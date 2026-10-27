#!/usr/bin/env bash
# Plan/apply dedicated Kubernetes RBAC groups and normalize the Kubernetes OIDC mappings.
# Default is read-only. Apply explicitly with: AK_APPLY=1 bash kubernetes-rbac.sh
set -euo pipefail

NS="${AK_NS:-authentik}"
CONTEXT="${KUBE_CONTEXT:-minicloud-oidc}"
POD=$(kubectl --context "$CONTEXT" get pod -n "$NS" -l app.kubernetes.io/component=server \
  -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod in namespace $NS" >&2; exit 1; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

kubectl --context "$CONTEXT" exec -i -n "$NS" "$POD" -- env AK_APPLY="${AK_APPLY:-0}" \
  ak shell < "$HERE/kubernetes-rbac.py"
