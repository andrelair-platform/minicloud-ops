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
# GLPI stores all of this in its MariaDB (config = glpi_configs, clients = glpi_apiclients, the user
# token = glpi_users.api_token) — so this is an idempotent SQL upsert, reproducible after a DB restore,
# not UI click-ops (same pattern as configure-sso-provider.sh).
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

# 2. an unrestricted active apiclient with an app_token (create once; reuse its token on re-run)
APP_TOKEN=$(run "SELECT app_token FROM glpi_apiclients WHERE name='$CLIENT_NAME' LIMIT 1;")
if [ -z "$APP_TOKEN" ]; then
  APP_TOKEN=$(openssl rand -hex 20)   # GLPI tokens are 40 hex chars
  run "INSERT INTO glpi_apiclients
        (entities_id,is_recursive,name,is_active,ipv4_range_start,ipv4_range_end,app_token,app_token_date,dolog_method,date_creation,date_mod)
       VALUES (0,1,'$CLIENT_NAME',1,NULL,NULL,'$APP_TOKEN',NOW(),0,NOW(),NOW());"
  echo "created apiclient '$CLIENT_NAME' (unrestricted, active)"
else
  run "UPDATE glpi_apiclients SET is_active=1, ipv4_range_start=NULL, ipv4_range_end=NULL WHERE name='$CLIENT_NAME';"
  echo "apiclient '$CLIENT_NAME' already exists (ensured active + unrestricted)"
fi

# 3. a user-level api_token on the service user (reuse if present)
USER_TOKEN=$(run "SELECT api_token FROM glpi_users WHERE name='$API_USER' AND api_token IS NOT NULL AND api_token<>'' LIMIT 1;")
if [ -z "$USER_TOKEN" ]; then
  USER_TOKEN=$(openssl rand -hex 20)
  run "UPDATE glpi_users SET api_token='$USER_TOKEN', api_token_date=NOW() WHERE name='$API_USER';"
  echo "minted api_token for user '$API_USER'"
else
  echo "user '$API_USER' already has an api_token (reused)"
fi

# 4. write both tokens into Vault secret/<VAULT_PATH> (never echoed). GLPI in-cluster base =
#    http://glpi.<ns>.svc. ESO (ExternalSecret n8n-hr-glpi) renders the k8s Secret from here.
API_URL="http://glpi.${NS}.svc/apirest.php"
OPS=$(cat ~/.vault-ops-token)
AGE_ID=$(/usr/bin/curl -s --cacert "$VCA" -H "X-Vault-Token: $OPS" \
  "$VADDR/v1/secret/data/platform/k3s-backup-age" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"]["identity"])')
ROOT=$(printf '%s' "$AGE_ID" | ~/.local/bin/age -d -i /dev/stdin ~/.vault-root-token.age)
[ -n "$ROOT" ] || { echo "ERROR: could not decrypt Vault root token" >&2; exit 1; }
# merge-safe write (overwrites the three keys at the path; GLPI DB remains the token source of truth)
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
echo "ESO ExternalSecret n8n-hr-glpi will render the k8s Secret from Vault (refresh ~1h; force: kubectl -n automation delete externalsecret n8n-hr-glpi --wait=false then re-sync)."
echo "GLPI API enabled + credentials provisioned."
