#!/usr/bin/env bash
# Rewrite the HOST inside a connection string stored in Vault (KV v2), keeping the embedded password.
#
# WHY: when a DB is migrated from a plain StatefulSet to a CNPG cluster (datastore-selection.md), the app's
# connection string in Vault still points at the old STS host. The cutover is first done with a reversible
# ESO target.template host-rewrite (no Vault write needed); this script makes Vault canonical again so that
# ES template can be removed. Only the host token is swapped — the password and the rest are untouched.
#
# WHERE IT RUNS: the controller (reaches the Vault API). Needs a BREAK-GLASS VAULT_TOKEN with read+update on
# secret/data/platform/* (the root token — the ops token has none; see ops-runbooks Controller secret
# hygiene). Nothing is baked in; the token comes from the environment.
#
# INPUTS (argv):  <vault-path> <property> <old-host> <new-host>
#   vault-path : KV v2 path under secret/data/  (e.g. platform/ktayl-prod)
#   property   : the JSON key holding the connection string (e.g. DSN, database-url)
#   old-host   : host substring to replace (e.g. ktayl-postgres.ktayl-prod.svc.cluster.local)
#   new-host   : replacement (e.g. ktayl-cnpg-rw.ktayl-prod.svc.cluster.local)
# ENV: VAULT_TOKEN (required, break-glass) · VAULT_ADDR (default https://vault.devandre.sbs) · CACERT
#   (default ~/minicloud-ca.crt).
#
# EXAMPLE (on the controller, with the decrypted root token):
#   VAULT_TOKEN=$(cat ~/.vault-root-token) \
#     bash scripts/vault/fix-db-host.sh platform/ktayl-prod DSN \
#       ktayl-postgres.ktayl-prod.svc.cluster.local ktayl-cnpg-rw.ktayl-prod.svc.cluster.local
#
# Idempotent: if the property already contains new-host, it is a no-op. The password is never printed.
set -euo pipefail
VAULT_ADDR="${VAULT_ADDR:-https://vault.devandre.sbs}"
CACERT="${CACERT:-$HOME/minicloud-ca.crt}"
: "${VAULT_TOKEN:?set VAULT_TOKEN (break-glass root; the ops token has no write on secret/platform/*)}"
VP="$1"; PROP="$2"; OLD="$3"; NEW="$4"

curl() { command curl -sk --cacert "$CACERT" -H "X-Vault-Token: $VAULT_TOKEN" "$@"; }
mask() { sed -E 's|://([^:@/]+):[^@]*@|://\1:****@|g'; }

cur=$(curl "$VAULT_ADDR/v1/secret/data/$VP" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['data'].get('$PROP',''))")
[ -z "$cur" ] && { echo "ERROR: property '$PROP' not found at secret/$VP"; exit 1; }
echo "  current $PROP host: $(echo "$cur" | sed -E 's|.*@([^/?]+).*|\1|')  (masked: $(echo "$cur" | mask | head -c 90))"
if ! echo "$cur" | grep -q "$OLD"; then
  if echo "$cur" | grep -q "$NEW"; then echo "  already points at $NEW — no-op."; exit 0; fi
  echo "ERROR: neither old ($OLD) nor new ($NEW) host found in $PROP — refusing to guess."; exit 1
fi
new=$(echo "$cur" | sed "s|$OLD|$NEW|g")
# KV v2 merge-patch: only this property changes; others preserved.
payload=$(python3 -c "import json,sys;print(json.dumps({'data':{'$PROP':sys.argv[1]}}))" "$new")
resp=$(printf '%s' "$payload" | curl -H "Content-Type: application/merge-patch+json" -X PATCH --data-binary @- "$VAULT_ADDR/v1/secret/data/$VP")
ver=$(echo "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin).get('data',{}).get('version','?'))" 2>/dev/null || echo "?")
[ "$ver" = "?" ] && { echo "WRITE FAILED: $(echo "$resp" | head -c 200)"; exit 1; }
echo "  WROTE $PROP host -> $NEW  (Vault KV version $ver)"
# verify
check=$(curl "$VAULT_ADDR/v1/secret/data/$VP" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['data']['$PROP'])" | sed -E 's|.*@([^/?]+).*|\1|')
echo "  verified host now: $check"
