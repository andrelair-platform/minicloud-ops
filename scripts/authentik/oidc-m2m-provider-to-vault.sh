#!/usr/bin/env bash
# M2M twin of oidc-provider-to-vault.sh: create (idempotently) an Authentik OAuth2 **client-credentials**
# provider+application AND store its client credentials + token endpoint + requested scope in Vault — so a
# new M2M consumer is one command. The client secret is born in the authentik pod, captured into a
# controller shell var, and written straight to Vault; it is never printed (only the non-secret client_id +
# the resulting KV version are echoed).
#
# RUN ON THE CONTROLLER. Requires: kubectl (authentik ns), ~/.vault-ops-token, ~/minicloud-ca.crt,
# ~/.local/bin/age, and the break-glass ~/.vault-root-token.age. Break-glass mechanism (referenced, not
# embedded — ops-runbooks "Controller Secret Hygiene"): the age identity is read from Vault with the
# read-only ops token, used to decrypt the root token, which performs the Vault write (platform secrets are
# not writable by the ops token by design).
#
# Usage: oidc-m2m-provider-to-vault.sh <slug> <display-name> <extra-scopes-csv> <vault-kv-path>
# Example: oidc-m2m-provider-to-vault.sh ktayl-core-uw-m2m "ktayl-core -> underwriting (M2M)" \
#            underwriting:write platform/ktayl-core-underwriting
#
# <extra-scopes-csv> = the consumer's required `scope` claims (ScopeMapping.scope_name), beyond openid; the
# client requests exactly these. Stores: oidc-client-id, oidc-client-secret, oidc-token-uri (Authentik's
# GLOBAL client-credentials token endpoint — the iss stamped into the token is the provider's, but the
# token endpoint is global), oidc-scope. Writes the KV path in full (dedicated M2M path → create/overwrite).
set -euo pipefail
umask 077
SLUG="${1:?slug required}"; NAME="${2:?display-name required}"
SCOPES="${3:?extra-scopes-csv required, e.g. underwriting:write}"; KVPATH="${4:?vault kv path required}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
V=https://vault.10.0.0.200.nip.io; CA="$HOME/minicloud-ca.crt"; OPS=$(cat "$HOME/.vault-ops-token")
TOKEN_URI="http://authentik-server.authentik.svc/application/o/token/"

# 1. create the M2M provider+app via the ORM (with the extra scope attached); capture the creds (not echoed)
OUT=$(bash "$HERE/oidc-m2m-provider.sh" "$SLUG" "$NAME" "$SCOPES")
CID=$(printf '%s' "$OUT" | sed -n 's/^CLIENTID=//p' | tr -d '\r')
CSEC=$(printf '%s' "$OUT" | sed -n 's/^CLIENTSECRET=//p' | tr -d '\r')
[ -n "$CID" ] && [ -n "$CSEC" ] || { echo "ERROR: provider creation returned no creds:"; echo "$OUT"; exit 1; }

# 2. break-glass: age identity (from Vault) -> decrypt the Vault root token
IDFILE=$(mktemp); trap 'shred -u "$IDFILE" 2>/dev/null || rm -f "$IDFILE"' EXIT
/usr/bin/curl -s --cacert "$CA" -H "X-Vault-Token: $OPS" \
  "$V/v1/secret/data/platform/k3s-backup-age" \
  | python3 -c "import sys,json; sys.stdout.write(json.load(sys.stdin)['data']['data']['identity'])" > "$IDFILE"
[ -s "$IDFILE" ] || { echo "ERROR: could not read age identity"; exit 1; }
ROOT=$("$HOME/.local/bin/age" -d -i "$IDFILE" "$HOME/.vault-root-token.age")

# 3. write the KV path (dedicated M2M path → full create/overwrite of the four keys)
PAYLOAD=$(CID="$CID" CSEC="$CSEC" TU="$TOKEN_URI" SC="$SCOPES" python3 -c \
  "import os,json; print(json.dumps({'data':{'oidc-client-id':os.environ['CID'],'oidc-client-secret':os.environ['CSEC'],'oidc-token-uri':os.environ['TU'],'oidc-scope':os.environ['SC']}}))")
RESP=$(printf '%s' "$PAYLOAD" | /usr/bin/curl -s --cacert "$CA" -H "X-Vault-Token: $ROOT" \
  -H "Content-Type: application/json" -X POST "$V/v1/secret/data/$KVPATH" --data @-)
unset ROOT PAYLOAD CSEC OPS

echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('WROTE $KVPATH version', d['data']['version']) if 'data' in d else sys.exit('ERROR: '+json.dumps(d))"
echo "client_id=$CID"
