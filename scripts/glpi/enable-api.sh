#!/usr/bin/env bash
# Enable (idempotently) the GLPI REST API and provision the credentials the HR-12 n8n fan-out needs:
#   - config enable_api=1 (enable_api_login_external_token is already on → user-token login works);
#   - an unrestricted, active apiclient with a random app_token (the existing "localhost" client is
#     IP-restricted, so n8n in another pod can't use it);
#   - a user-level api_token (personal token) on a service user so initSession can authenticate.
# Both tokens are written straight into a k8s Secret (default: automation/n8n-hr-glpi) for n8n to
# consume as env — they are NEVER echoed to the terminal or placed in argv.
#
# GLPI stores all of this in its MariaDB (config = glpi_configs, clients = glpi_apiclients, the user
# token = glpi_users.api_token) — so this is an idempotent SQL upsert, reproducible after a DB restore,
# not UI click-ops (same pattern as configure-sso-provider.sh).
#
# RUN ON THE CONTROLLER. Requires kubectl (itsm + the target ns).
# Usage:  scripts/glpi/enable-api.sh [glpi-ns] [db-secret] [api-user] [target-ns] [target-secret]
# Example: scripts/glpi/enable-api.sh itsm ktayl-itsm-db glpi automation n8n-hr-glpi
set -euo pipefail
umask 077
NS="${1:-itsm}"
DB_SECRET="${2:-ktayl-itsm-db}"
API_USER="${3:-glpi}"             # the GLPI user whose personal api_token identifies the API caller
TGT_NS="${4:-automation}"         # where n8n runs
TGT_SECRET="${5:-n8n-hr-glpi}"
CLIENT_NAME="n8n-hr-fanout"

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

# 4. write both tokens into the n8n-side k8s secret (never echoed). GLPI in-cluster base = http://glpi.<ns>.svc
kubectl create secret generic "$TGT_SECRET" -n "$TGT_NS" \
  --from-literal=GLPI_APP_TOKEN="$APP_TOKEN" \
  --from-literal=GLPI_USER_TOKEN="$USER_TOKEN" \
  --from-literal=GLPI_API_URL="http://glpi.${NS}.svc/apirest.php" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
echo "wrote $TGT_NS/$TGT_SECRET (GLPI_APP_TOKEN, GLPI_USER_TOKEN, GLPI_API_URL) — tokens not printed"
echo "GLPI API enabled + credentials provisioned."
