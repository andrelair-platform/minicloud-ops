#!/usr/bin/env bash
# Provision ktayl-iam's onboarding credentials into Vault (secret/platform/ktayl-iam), idempotently:
#   1. the shared DEFAULT initial password (DEFAULT_PW env)         -> key default-mailbox-password
#   2. a SCOPED elevated Authentik token for set_password at Joiner -> key authentik-credential-token
#
# The Authentik token belongs to a dedicated SERVICE_ACCOUNT 'ktayl-iam-credential-svc' granted ONLY
# the `authentik_core.reset_user_password` permission (not admin) — so the ktayl-iam sync token stays
# least-privilege (threat T4) and this one privilege is isolated.
#
# Break-glass: the Vault ROOT token is decrypted on the fly from ~/.vault-root-token.age using the age
# identity read from Vault with the on-disk ops token. NO secret value is ever printed (only versions /
# key names / DONE). Temp files are shredded. Run ON THE CONTROLLER.
#
#   DEFAULT_PW='<the shared default initial password>' bash provision-iam-credential.sh
#
# Re-runnable: reuses the existing service account + token (same key) and only re-patches Vault.
# pyright: reportMissingImports=false   (the python block runs inside the authentik pod via `ak shell`)
set -euo pipefail
: "${DEFAULT_PW:?set DEFAULT_PW to the shared default initial password}"

V=https://vault.10.0.0.200.nip.io
VP="${VAULT_PATH:-platform/ktayl-iam}"   # dev: platform/ktayl-iam · prod: platform/ktayl-iam-prod
OPS=$(cat ~/.vault-ops-token)
TMP=$(mktemp -d)
trap 'find "$TMP" -type f -exec shred -u {} + 2>/dev/null; rmdir "$TMP" 2>/dev/null || true' EXIT

# 1. age identity (ops-token read) -> decrypt the Vault root token (never printed)
curl -sk -H "X-Vault-Token: $OPS" "$V/v1/secret/data/platform/k3s-backup-age" \
  | python3 -c 'import sys,json;sys.stdout.write(json.load(sys.stdin)["data"]["data"]["identity"])' > "$TMP/id.age"
ROOT=$(~/.local/bin/age -d -i "$TMP/id.age" ~/.vault-root-token.age)
[ -n "$ROOT" ] || { echo "ERROR: could not decrypt the Vault root token"; exit 1; }

# 2. Authentik scoped service account + reset_user_password perm + non-expiring API token (idempotent)
AK_POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server -o name | head -1)
AKTOKEN=$(kubectl exec -i -n authentik "$AK_POD" -- ak shell <<'PY' 2>/dev/null | grep '^TOKENKEY=' | cut -d= -f2- || true
# Authentik RBAC grants permissions via a Role bound to a Group (not the Django user M2M). We scope a
# dedicated role to ONLY `authentik_core.reset_user_password`, bind it to a group, and put the service
# account in that group → the token can set passwords but nothing else (least-privilege, threat T4).
from authentik.core.models import User, Group, Token, TokenIntents, UserTypes
from authentik.rbac.models import Role
from guardian.shortcuts import assign_perm
sa, _ = User.objects.get_or_create(
    username="ktayl-iam-credential-svc",
    defaults={"name": "ktayl-iam credential svc", "type": UserTypes.SERVICE_ACCOUNT,
              "path": "users", "is_active": True},
)
role, _ = Role.objects.get_or_create(name="ktayl-iam-credential-role")
assign_perm("authentik_core.reset_user_password", role)  # idempotent
grp, _ = Group.objects.get_or_create(name="ktayl-iam-credential")
grp.roles.add(role)
grp.users.add(sa)
tok, _ = Token.objects.get_or_create(
    identifier="ktayl-iam-credential",
    defaults={"user": sa, "intent": TokenIntents.INTENT_API, "expiring": False,
              "description": "ktayl-iam elevated token: set_password at onboarding (reset_user_password only)"},
)
if tok.user_id != sa.pk:
    tok.user = sa
    tok.save()
print("TOKENKEY=" + tok.key)
PY
)
[ -n "$AKTOKEN" ] || { echo "ERROR: Authentik token creation failed"; exit 1; }

# 3. write BOTH into Vault (root token), KV v2 merge-patch -> existing keys preserved
curl -sk -H "X-Vault-Token: $ROOT" -H "Content-Type: application/merge-patch+json" \
  -X PATCH "$V/v1/secret/data/$VP" \
  -d "{\"data\":{\"default-mailbox-password\":\"$DEFAULT_PW\",\"authentik-credential-token\":\"$AKTOKEN\"}}" \
  | python3 -c 'import sys,json;print("Vault patched — new version:", json.load(sys.stdin)["data"]["version"])'

# 4. confirm (ops-token, key NAMES only — no values)
curl -sk -H "X-Vault-Token: $OPS" "$V/v1/secret/data/$VP" \
  | python3 -c 'import sys,json;print("keys now:", sorted(json.load(sys.stdin)["data"]["data"].keys()))'
echo "DONE — default password + scoped Authentik credential token provisioned (no secret printed)."
