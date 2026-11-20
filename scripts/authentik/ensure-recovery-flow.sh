#!/usr/bin/env bash
# Idempotently ensure an Authentik RECOVERY flow exists + is the default brand's recovery flow
# (ktayl-iam ADR-016), by running ensure-recovery-flow.py non-interactively in the authentik server pod.
# Without it, user-password recovery (and the external-collaborator invite link) is impossible —
# `createRecoveryLink` returns 400 "No recovery flow set".
#
# Usage:   scripts/authentik/ensure-recovery-flow.sh [<flow-slug>] [<flow-title>]
# Example: scripts/authentik/ensure-recovery-flow.sh
#
# Requires: kubectl context with access to the authentik namespace. Run on the controller.
# Run via ak-shell -c (not stdin): the interactive ak shell mangles a multi-statement script read on
# stdin; -c runs it non-interactively, and base64 keeps the payload quote-safe.
set -euo pipefail
FLOW_SLUG="${1:-ktayl-recovery-flow}"; FLOW_TITLE="${2:-Reset your password}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

B64=$(base64 < "$HERE/ensure-recovery-flow.py" | tr -d '\n')
kubectl exec -i -n authentik "$POD" -- \
  env AK_FLOW_SLUG="$FLOW_SLUG" AK_FLOW_TITLE="$FLOW_TITLE" \
  ak shell -c "import base64; exec(base64.b64decode('$B64').decode())"
