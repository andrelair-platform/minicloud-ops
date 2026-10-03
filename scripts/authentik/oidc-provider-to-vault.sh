#!/usr/bin/env bash
# Create (idempotently) an Authentik OIDC provider+application for an app AND store its client
# credentials in Vault — so a new OIDC app is one command. The client secret is born in the
# authentik pod, captured into a controller shell var, and written straight to Vault; it is never
# printed (only the non-secret client_id + the resulting KV version are echoed).
#
# RUN ON THE CONTROLLER. Requires: kubectl (authentik ns), ~/.vault-ops-token, ~/minicloud-ca.crt,
# ~/.local/bin/age, and the break-glass ~/.vault-root-token.age. Break-glass mechanism (referenced,
# not embedded — see ops-runbooks "Controller Secret Hygiene"): the age identity is read from Vault
# with the read-only ops token, used to decrypt the root token, which performs the Vault write
# (platform secrets are not writable by the ops token by design).
#
# Usage: oidc-provider-to-vault.sh <slug> <display-name> <redirect-uri>[,<uri>...] <vault-kv-path>
# Example: oidc-provider-to-vault.sh bookstack BookStack \
#            https://intranet.devandre.sbs/oidc/callback platform/bookstack
#
# The Vault KV-v2 path must already exist (uses merge-patch to add oidc-client-id/oidc-client-secret
# without clobbering existing keys like the DB creds + app-key).
set -euo pipefail
umask 077
SLUG="${1:?slug required}"; NAME="${2:?display-name required}"
REDIRECTS="${3:?redirect-uri(s) required}"; KVPATH="${4:?vault kv path required, e.g. platform/bookstack}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
V=https://vault.10.0.0.200.nip.io; CA="$HOME/minicloud-ca.crt"; OPS=$(cat "$HOME/.vault-ops-token")

# 1. create the provider+app via the ORM; capture the creds (not echoed)
OUT=$(bash "$HERE/oidc-provider.sh" "$SLUG" "$NAME" "$REDIRECTS")
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

# 3. merge-patch the KV path (preserves existing keys)
PAYLOAD=$(CID="$CID" CSEC="$CSEC" python3 -c \
  "import os,json; print(json.dumps({'data':{'oidc-client-id':os.environ['CID'],'oidc-client-secret':os.environ['CSEC']}}))")
RESP=$(printf '%s' "$PAYLOAD" | /usr/bin/curl -s --cacert "$CA" -H "X-Vault-Token: $ROOT" \
  -H "Content-Type: application/merge-patch+json" -X PATCH "$V/v1/secret/data/$KVPATH" --data @-)
unset ROOT PAYLOAD CSEC OPS

echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('PATCHED $KVPATH version', d['data']['version']) if 'data' in d else sys.exit('ERROR: '+json.dumps(d))"
echo "client_id=$CID"
