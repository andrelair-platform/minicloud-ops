#!/usr/bin/env bash
# Configure (idempotently) a GLPI singlesignon OIDC provider row pointing at Authentik.
#
# GLPI's glpi-singlesignon plugin stores each identity provider as a ROW in its own DB table
# (glpi_plugin_singlesignon_providers), NOT as env/config — so wiring SSO = an idempotent upsert of
# that row with the OIDC client creds + Authentik's authorize/token/userinfo endpoints. This makes
# the wiring reproducible (re-run after a DB restore / fresh install) instead of hand-clicking the
# GLPI "Setup > Plugins > SingleSignOn" UI.
#
# RUN ON THE CONTROLLER. Requires: kubectl (the GLPI ns), ~/.vault-ops-token, ~/minicloud-ca.crt.
# The OIDC client_id/secret are READ from Vault with the read-only ops token (platform/* is readable;
# only writes need break-glass). The secret is piped into the DB over stdin — it is NEVER echoed to
# the terminal or placed in argv (only the non-secret provider name + resulting row id are printed).
#
# Prereq: the plugin must already be installed + activated:
#   kubectl exec <glpi-pod> -c glpi -- php /var/www/glpi/bin/console glpi:plugin:install singlesignon
#   kubectl exec <glpi-pod> -c glpi -- php /var/www/glpi/bin/console glpi:plugin:activate singlesignon
#
# Usage: configure-sso-provider.sh <ns> <provider-name> <authentik-base-url> <vault-kv-path> [db-secret] [scope]
# Example:
#   configure-sso-provider.sh itsm Authentik https://auth.devandre.sbs platform/ktayl-itsm \
#       ktayl-itsm-db "openid email profile"
set -euo pipefail
umask 077

NS="${1:?namespace required (e.g. itsm)}"
PNAME="${2:?provider display-name required (e.g. Authentik)}"
AK_BASE="${3:?authentik base url required (e.g. https://auth.devandre.sbs)}"
KVPATH="${4:?vault kv path required (e.g. platform/ktayl-itsm)}"
DB_SECRET="${5:-ktayl-itsm-db}"            # k8s secret holding db-password (key: db-password)
SCOPE="${6:-openid email profile}"

V=https://vault.10.0.0.200.nip.io
CA="$HOME/minicloud-ca.crt"
OPS="$(cat "$HOME/.vault-ops-token")"

AK_BASE="${AK_BASE%/}"                      # strip trailing slash
URL_AUTHORIZE="${AK_BASE}/application/o/authorize/"
URL_TOKEN="${AK_BASE}/application/o/token/"
URL_USERINFO="${AK_BASE}/application/o/userinfo/"

# 1. read the OIDC client creds from Vault (ops token = read-only on platform/*) — not echoed
RESP=$(curl -sk --cacert "$CA" -H "X-Vault-Token: $OPS" "$V/v1/secret/data/$KVPATH")
CID=$(printf '%s' "$RESP" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["data"]["oidc-client-id"])')
CSEC=$(printf '%s' "$RESP" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["data"]["oidc-client-secret"])')
[ -n "$CID" ] && [ -n "$CSEC" ] || { echo "ERROR: Vault $KVPATH has no oidc-client-id/oidc-client-secret"; exit 1; }

# 2. locate the GLPI MariaDB pod + read its password from the k8s secret (not echoed)
MPOD=$(kubectl get pods -n "$NS" -l app=glpi-mariadb -o jsonpath='{.items[0].metadata.name}')
[ -n "$MPOD" ] || { echo "ERROR: no glpi-mariadb pod in ns $NS"; exit 1; }
DBPASS=$(kubectl get secret "$DB_SECRET" -n "$NS" -o jsonpath='{.data.db-password}' | base64 -d)

# 3. idempotent upsert of the provider row (match on name; the table has no unique key on name,
#    so we check-then-insert/update). SQL is piped over stdin; creds never hit argv. MYSQL_PWD via env.
#    type='generic' makes the plugin use the stored url_* + scope verbatim; use_email_for_login=1 keys
#    the GLPI account off the OIDC email (clean SSO login + auto-provision on first sign-in).
run_sql() { kubectl exec -i "$MPOD" -n "$NS" --env="MYSQL_PWD=$DBPASS" -- mariadb -uglpi glpi -N "$@" 2>/dev/null; }

# SQL-escape single quotes in values
esc() { printf '%s' "$1" | sed "s/'/''/g"; }
E_PNAME=$(esc "$PNAME"); E_CID=$(esc "$CID"); E_CSEC=$(esc "$CSEC"); E_SCOPE=$(esc "$SCOPE")
E_AUTH=$(esc "$URL_AUTHORIZE"); E_TOK=$(esc "$URL_TOKEN"); E_UI=$(esc "$URL_USERINFO")

EXISTING=$(run_sql -e "SELECT id FROM glpi_plugin_singlesignon_providers WHERE name='$E_PNAME' AND is_deleted=0 LIMIT 1;")

if [ -n "$EXISTING" ]; then
  run_sql <<SQL
UPDATE glpi_plugin_singlesignon_providers SET
  type='generic', client_id='$E_CID', client_secret='$E_CSEC', scope='$E_SCOPE',
  url_authorize='$E_AUTH', url_access_token='$E_TOK', url_resource_owner_details='$E_UI',
  is_active=1, use_email_for_login=1, popup=0, date_mod=NOW()
WHERE id=$EXISTING;
SQL
  echo "updated GLPI singlesignon provider '$PNAME' (id=$EXISTING) in ns $NS"
else
  run_sql <<SQL
INSERT INTO glpi_plugin_singlesignon_providers
  (type, name, client_id, client_secret, scope, url_authorize, url_access_token,
   url_resource_owner_details, is_active, use_email_for_login, popup, date_creation, date_mod)
VALUES
  ('generic', '$E_PNAME', '$E_CID', '$E_CSEC', '$E_SCOPE', '$E_AUTH', '$E_TOK',
   '$E_UI', 1, 1, 0, NOW(), NOW());
SQL
  NEWID=$(run_sql -e "SELECT id FROM glpi_plugin_singlesignon_providers WHERE name='$E_PNAME' AND is_deleted=0 LIMIT 1;")
  echo "created GLPI singlesignon provider '$PNAME' (id=$NEWID) in ns $NS"
fi

echo "authorize=$URL_AUTHORIZE"
echo "token=$URL_TOKEN  userinfo=$URL_USERINFO  scope=$SCOPE  use_email_for_login=1"
