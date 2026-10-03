#!/usr/bin/env bash
# Bootstrap a BookStack **service admin + API token** and store the token in Vault — so content can be
# seeded via the REST API without a human UI login. The token secret is born in the pod, captured into a
# controller shell var, and written straight to Vault; only the non-secret token_id is echoed.
#
# RUN ON THE CONTROLLER. Requires: kubectl (intranet ns), ~/.vault-ops-token, ~/minicloud-ca.crt,
# ~/.local/bin/age, ~/.vault-root-token.age (break-glass — same mechanism as the authentik helper).
#
# Usage: bootstrap-token-to-vault.sh [service-email] [service-name] [vault-kv-path]
#   defaults: bootstrap@intranet.local  "Content Bootstrap"  platform/bookstack
# Stores Vault key `api-token` = "<token_id>:<secret>" (merge-patch; preserves existing keys).
set -euo pipefail
umask 077
NS=intranet
EMAIL="${1:-bootstrap@intranet.local}"; NAME="${2:-Content Bootstrap}"; KVPATH="${3:-platform/bookstack}"
V=https://vault.10.0.0.200.nip.io; CA="$HOME/minicloud-ca.crt"; OPS=$(cat "$HOME/.vault-ops-token")
POD=$(kubectl get pod -n "$NS" -l app=bookstack -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no bookstack pod" >&2; exit 1; }

# 1. ensure the service admin exists (idempotent; password machine-random, not needed afterwards)
PW=$(openssl rand -base64 24)
kubectl exec -n "$NS" "$POD" -c bookstack -- \
  php /app/www/artisan bookstack:create-admin --email="$EMAIL" --name="$NAME" --password="$PW" >/dev/null 2>&1 || true

# 2. create an API token on that user via tinker; capture token_id:secret (not echoed)
PHP='$u=\BookStack\Users\Models\User::where("email","'"$EMAIL"'")->first();
$t=new \BookStack\Api\ApiToken();$t->user_id=$u->id;$t->name="content-bootstrap";
$t->token_id=\Illuminate\Support\Str::random(32);$s=\Illuminate\Support\Str::random(32);
$t->secret=\Illuminate\Support\Facades\Hash::make($s);$t->expires_at=now()->addYears(5);$t->save();
echo "APITOKEN=".$t->token_id.":".$s;'
OUT=$(printf '%s' "$PHP" | kubectl exec -i -n "$NS" "$POD" -c bookstack -- php /app/www/artisan tinker 2>/dev/null)
TOKEN=$(printf '%s' "$OUT" | sed -n 's/.*APITOKEN=\([A-Za-z0-9]*:[A-Za-z0-9]*\).*/\1/p' | head -1)
[ -n "$TOKEN" ] || { echo "ERROR: token not created:"; echo "$OUT"; exit 1; }

# 3. break-glass: age identity (Vault, ops token) -> decrypt root -> merge-patch the api-token
IDFILE=$(mktemp); trap 'shred -u "$IDFILE" 2>/dev/null || rm -f "$IDFILE"' EXIT
/usr/bin/curl -s --cacert "$CA" -H "X-Vault-Token: $OPS" "$V/v1/secret/data/platform/k3s-backup-age" \
  | python3 -c "import sys,json; sys.stdout.write(json.load(sys.stdin)['data']['data']['identity'])" > "$IDFILE"
ROOT=$("$HOME/.local/bin/age" -d -i "$IDFILE" "$HOME/.vault-root-token.age")
PAYLOAD=$(TOK="$TOKEN" python3 -c "import os,json; print(json.dumps({'data':{'api-token':os.environ['TOK']}}))")
RESP=$(printf '%s' "$PAYLOAD" | /usr/bin/curl -s --cacert "$CA" -H "X-Vault-Token: $ROOT" \
  -H "Content-Type: application/merge-patch+json" -X PATCH "$V/v1/secret/data/$KVPATH" --data @-)
unset ROOT PAYLOAD TOKEN OPS
echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('stored api-token in $KVPATH version', d['data']['version']) if 'data' in d else sys.exit('ERROR: '+json.dumps(d))"
