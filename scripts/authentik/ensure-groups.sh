#!/usr/bin/env bash
# Idempotently ensure Authentik groups exist (+ optionally add one member), by piping
# ensure-groups.py into `ak shell` in the authentik server pod. Creates the per-module
# authorization groups a service's @PreAuthorize gate checks.
#
# Usage:  scripts/authentik/ensure-groups.sh "<group1>[,<group2>...]" [<member-username>]
# Example: scripts/authentik/ensure-groups.sh "Complaints Handler,Finance" kanmegnea
#
# Requires: kubectl context with access to the `authentik` namespace. Run on the controller.
set -euo pipefail
GROUPS="${1:?groups required (comma/newline separated)}"; MEMBER="${2:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

kubectl exec -i -n authentik "$POD" -- \
  env AK_GROUPS="$GROUPS" AK_MEMBER="$MEMBER" ak shell < "$HERE/ensure-groups.py"
