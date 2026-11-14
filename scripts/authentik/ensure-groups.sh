#!/usr/bin/env bash
# Idempotently ensure Authentik groups exist (+ optionally add one member), by running
# ensure-groups.py non-interactively in the authentik server pod. Creates the per-module
# authorization groups a service's PreAuthorize gate checks.
#
# Usage:   scripts/authentik/ensure-groups.sh "<group1>[,<group2>...]" [<member-username>]
# Example: scripts/authentik/ensure-groups.sh "Complaints Handler,Finance" 100001
#
# Requires: kubectl context with access to the authentik namespace. Run on the controller.
#
# GOTCHA: do NOT name the groups variable GROUPS -- that is a bash BUILT-IN readonly array (the current
# user's group IDs); assigning to it is ignored, so "$GROUPS" expands to the user's primary GID (e.g.
# 1000) and the wrong group gets created. Use a non-special name (GROUP_NAMES).
# Run via ak-shell -c (not stdin): the interactive ak shell mangles a multi-statement script read on
# stdin; -c runs it non-interactively, and base64 keeps the payload quote-safe.
set -euo pipefail
GROUP_NAMES="${1:?groups required (comma/newline separated)}"; MEMBER="${2:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

B64=$(base64 < "$HERE/ensure-groups.py" | tr -d '\n')
kubectl exec -i -n authentik "$POD" -- \
  env AK_GROUPS="$GROUP_NAMES" AK_MEMBER="$MEMBER" \
  ak shell -c "import base64; exec(base64.b64decode('$B64').decode())"
