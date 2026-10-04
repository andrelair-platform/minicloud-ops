#!/usr/bin/env bash
# Grant an Authentik service account a least-privilege group-management permission set, by piping
# grant-service-group-perms.py into `ak shell`. Default perms = view_user,view_group,add_group,
# change_group (enough to create groups + add/remove members; nothing else — threat T4).
#
# Usage:  scripts/authentik/grant-service-group-perms.sh <svc-username> [perm,perm,...]
# Example: scripts/authentik/grant-service-group-perms.sh ktayl-iam-svc
#
# Requires: kubectl context with access to the `authentik` namespace. Run on the controller.
set -euo pipefail
SVC="${1:?service-account username required}"; PERMS="${2:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

kubectl exec -i -n authentik "$POD" -- \
  env AK_SVC_USERNAME="$SVC" ${PERMS:+AK_PERMS="$PERMS"} \
  ak shell < "$HERE/grant-service-group-perms.py"
