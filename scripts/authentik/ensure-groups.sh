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
# Why ak-shell-dash-c (not stdin): the INTERACTIVE ak shell mangles a multi-statement script read on
# stdin (os.environ came back wrong, yielding a bogus group name). Running the code non-interactively
# via the -c flag fixes it; base64 keeps the payload quote-safe regardless of the py file content.
# NOTE: keep this comment block free of backticks + decimal tokens -- a stray one corrupted the parse.
set -euo pipefail
GROUPS="${1:?groups required (comma/newline separated)}"; MEMBER="${2:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

B64=$(base64 < "$HERE/ensure-groups.py" | tr -d '\n')
kubectl exec -i -n authentik "$POD" -- \
  env AK_GROUPS="$GROUPS" AK_MEMBER="$MEMBER" \
  ak shell -c "import base64; exec(base64.b64decode('$B64').decode())"
