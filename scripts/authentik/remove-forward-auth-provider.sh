#!/usr/bin/env bash
# DELETE an Authentik forward-auth (proxy) Application + its ProxyProvider + group binding, and detach it
# from the embedded outpost — by piping remove-forward-auth-provider.py into `ak shell` in the authentik
# server pod. The decommission counterpart of forward-auth-provider.sh (run when an SSO'd app is retired).
#
# Usage:   scripts/authentik/remove-forward-auth-provider.sh <slug>
# Example: scripts/authentik/remove-forward-auth-provider.sh adminer
#   <slug> — the application slug; the provider is assumed to be named "<slug>-forward-auth"
#            (the convention forward-auth-provider.sh creates). Idempotent — no-ops if already gone.
# Requires a kubectl context with access to the `authentik` namespace. Run on the controller.
set -euo pipefail
SLUG="${1:?slug required}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

# remove-forward-auth-provider.py reads NAME/SLUG from globals() — prepend the Python assignments.
{ echo "NAME='${SLUG}-forward-auth'; SLUG='${SLUG}'"
  cat "$HERE/remove-forward-auth-provider.py"
} | kubectl exec -i -n authentik "$POD" -- ak shell
