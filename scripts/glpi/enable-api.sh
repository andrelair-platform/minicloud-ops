#!/usr/bin/env bash
# Enable (idempotently) the GLPI REST API and provision the credentials the HR-12 n8n fan-out needs:
#   - config enable_api=1 (enable_api_login_external_token is already on → user-token login works);
#   - an unrestricted, active apiclient with a random app_token (the existing "localhost" client is
#     IP-restricted, so n8n in another pod can't use it);
#   - a user-level api_token (personal token) on a service user so initSession can authenticate.
# Both tokens are written to VAULT (secret/platform/glpi) — the platform's secret source of truth —
# from where ESO renders the k8s Secret automation/n8n-hr-glpi that n8n consumes as env. They are
# NEVER echoed to the terminal or placed in argv. (Earlier versions wrote the k8s Secret directly;
# that secret is now ESO-managed, so writing it here would fight ESO ownership — write Vault instead.)
#
# CRITICAL — GLPI 10 stores API tokens ENCRYPTED and the API ALWAYS runs GLPIKey::decrypt() on the
# stored app_token / user api_token before comparing (src/Api/API.php checkAppToken + User::getFromDBbyToken),
# UNCONDITIONALLY (regardless of the are_apiclients_tokens_encrypted config). So a raw-SQL *plaintext*
# token is rejected (ERROR_WRONG_APP_TOKEN_PARAMETER / ERROR_GLPI_LOGIN_USER_TOKEN). We therefore store
# GLPIKey::encrypt(plaintext) in GLPI (via a PHP snippet in the glpi pod) and the PLAINTEXT in Vault
# (what n8n sends). Vault is the token source of truth → re-running after a GLPI DB rebuild re-encrypts
# the same plaintext back into GLPI. (Learned 2026-10-05, HR-12 fan-out.)
#
# RUN ON THE CONTROLLER. Requires kubectl (itsm ns), curl, python3, age, and the Vault root token
# (decrypted from ~/.vault-root-token.age via the age identity in Vault secret/platform/k3s-backup-age,
# readable with ~/.vault-ops-token — the standard controller break-glass chain).
# Usage:  scripts/glpi/enable-api.sh [glpi-ns] [db-secret] [api-user] [vault-path]
# Example: scripts/glpi/enable-api.sh itsm ktayl-itsm-db glpi platform/glpi
set -euo pipefail
umask 077
NS="${1:-itsm}"
DB_SECRET="${2:-ktayl-itsm-db}"
API_USER="${3:-glpi}"             # the GLPI user whose personal api_token identifies the API caller
VAULT_PATH="${4:-platform/glpi}"  # Vault KV-v2 path (relative to the `secret` mount) ESO reads from
CLIENT_NAME="n8n-hr-fanout"
VADDR="https://vault.10.0.0.200.nip.io"; VCA="$HOME/minicloud-ca.crt"

MPOD=$(kubectl get pods -n "$NS" -l app=glpi-mariadb -o jsonpath='{.items[0].metadata.name}')
[ -n "$MPOD" ] || { echo "ERROR: no glpi-mariadb pod in ns $NS" >&2; exit 1; }
DBPASS=$(kubectl get secret "$DB_SECRET" -n "$NS" -o jsonpath='{.data.db-password}' | base64 -d)
run() { kubectl exec -i "$MPOD" -n "$NS" -- env MYSQL_PWD="$DBPASS" mariadb -uglpi glpi -N -e "$1"; }

# 1. enable the REST API
run "UPDATE glpi_configs SET value='1' WHERE name='enable_api';"
run "UPDATE glpi_configs SET value='1' WHERE name='enable_api_login_external_token';"
echo "enable_api=$(run "SELECT value FROM glpi_configs WHERE name='enable_api';")  login_external_token=$(run "SELECT value FROM glpi_configs WHERE name='enable_api_login_external_token';")"

# 2. decrypt the Vault root token (age chain) — needed to read/write Vault
API_URL="http://glpi.${NS}.svc/apirest.php"
OPS=$(cat ~/.vault-ops-token)
AGE_ID=$(/usr/bin/curl -s --cacert "$VCA" -H "X-Vault-Token: $OPS" \
  "$VADDR/v1/secret/data/platform/k3s-backup-age" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"]["identity"])')
ROOT=$(printf '%s' "$AGE_ID" | ~/.local/bin/age -d -i /dev/stdin ~/.vault-root-token.age)
[ -n "$ROOT" ] || { echo "ERROR: could not decrypt Vault root token" >&2; exit 1; }

# 3. determine the PLAINTEXT tokens — Vault is the source of truth (reuse if present, else generate).
#    (We must NOT read them back from GLPI: GLPI stores them encrypted — see the header note.)
read_vault() { # $1=property -> value or empty
  /usr/bin/curl -s --cacert "$VCA" -H "X-Vault-Token: $ROOT" "$VADDR/v1/secret/data/$VAULT_PATH" \
    | python3 -c "import sys,json
try:
  d=json.load(sys.stdin)['data']['data']; print(d.get('$1',''))
except Exception: print('')"
}
APP_TOKEN=$(read_vault app-token); [ -n "$APP_TOKEN" ] || APP_TOKEN=$(openssl rand -hex 20)
USER_TOKEN=$(read_vault user-token); [ -n "$USER_TOKEN" ] || USER_TOKEN=$(openssl rand -hex 20)

# 4. write the PLAINTEXT tokens to Vault (what n8n sends; ESO renders automation/n8n-hr-glpi from here)
VADDR="$VADDR" VCA="$VCA" ROOT="$ROOT" VPATH="$VAULT_PATH" \
APP_TOKEN="$APP_TOKEN" USER_TOKEN="$USER_TOKEN" API_URL="$API_URL" python3 - <<'PY'
import os,json,ssl,urllib.request
ctx=ssl.create_default_context(cafile=os.environ["VCA"])
body={"data":{"app-token":os.environ["APP_TOKEN"],"user-token":os.environ["USER_TOKEN"],"api-url":os.environ["API_URL"]}}
req=urllib.request.Request(f"{os.environ['VADDR']}/v1/secret/data/{os.environ['VPATH']}",
    data=json.dumps(body).encode(),
    headers={"X-Vault-Token":os.environ["ROOT"],"Content-Type":"application/json"},method="POST")
urllib.request.urlopen(req,context=ctx).read()
PY
echo "wrote Vault secret/$VAULT_PATH (app-token, user-token, api-url) — tokens not printed"

# 5. store the tokens in GLPI as GLPIKey-ENCRYPTED values (GLPI decrypts them to compare). Done in a
#    PHP snippet inside the glpi pod (needs GLPIKey + the crypt key); plaintext passed via env, not argv.
GLPIPOD=$(kubectl get pod -n "$NS" -l app=glpi -o jsonpath='{.items[0].metadata.name}')
[ -n "$GLPIPOD" ] || { echo "ERROR: no glpi pod in ns $NS" >&2; exit 1; }
cat <<'PHP' | kubectl exec -i "$GLPIPOD" -c glpi -n "$NS" -- sh -c 'cat > /tmp/glpi-enc.php'
<?php
define('GLPI_ROOT', '/var/www/glpi'); chdir(GLPI_ROOT);
include GLPI_ROOT . '/inc/includes.php';
global $DB;
$k = new GLPIKey();
$app = getenv('APP_PLAIN'); $usr = getenv('USER_PLAIN');
$client = getenv('CLIENT'); $apiuser = getenv('APIUSER');
$now = date('Y-m-d H:i:s');
$row = $DB->request(['SELECT'=>['id'],'FROM'=>'glpi_apiclients','WHERE'=>['name'=>$client]])->current();
if ($row) {
    $DB->update('glpi_apiclients', ['is_active'=>1,'ipv4_range_start'=>null,'ipv4_range_end'=>null,'ipv6'=>null,'app_token'=>$k->encrypt($app),'app_token_date'=>$now], ['id'=>$row['id']]);
    echo "apiclient '$client' updated (active, unrestricted, encrypted app_token)\n";
} else {
    $DB->insert('glpi_apiclients', ['entities_id'=>0,'is_recursive'=>1,'name'=>$client,'is_active'=>1,'ipv4_range_start'=>null,'ipv4_range_end'=>null,'app_token'=>$k->encrypt($app),'app_token_date'=>$now,'dolog_method'=>0,'date_creation'=>$now,'date_mod'=>$now]);
    echo "apiclient '$client' created (active, unrestricted, encrypted app_token)\n";
}
$u = $DB->request(['SELECT'=>['id'],'FROM'=>'glpi_users','WHERE'=>['name'=>$apiuser]])->current();
if (!$u) { fwrite(STDERR, "ERROR: GLPI user '$apiuser' not found\n"); exit(1); }
$DB->update('glpi_users', ['api_token'=>$k->encrypt($usr),'api_token_date'=>$now], ['id'=>$u['id']]);
echo "user '$apiuser' api_token set (encrypted)\n";
PHP
kubectl exec "$GLPIPOD" -c glpi -n "$NS" -- env APP_PLAIN="$APP_TOKEN" USER_PLAIN="$USER_TOKEN" CLIENT="$CLIENT_NAME" APIUSER="$API_USER" php /tmp/glpi-enc.php
kubectl exec "$GLPIPOD" -c glpi -n "$NS" -- rm -f /tmp/glpi-enc.php
# clear GLPI cache so it re-reads (config/clients)
kubectl exec "$GLPIPOD" -c glpi -n "$NS" -- sh -c 'cd /var/www/glpi && php bin/console cache:clear >/dev/null 2>&1' || true

echo "ESO ExternalSecret n8n-hr-glpi renders automation/n8n-hr-glpi from Vault (force: kubectl -n automation delete secret n8n-hr-glpi — ESO recreates)."
echo "GLPI API enabled + credentials provisioned (GLPIKey-encrypted in GLPI, plaintext in Vault)."
