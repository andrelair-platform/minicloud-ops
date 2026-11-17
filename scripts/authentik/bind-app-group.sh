#!/usr/bin/env bash
# Idempotently bind an Authentik Application (by slug) to a GROUP for access (ADDITIVE — existing
# bindings untouched; the app's policy engine is `any`). The 'who may reach the app' layer that
# complements a tool's in-app role mapping (platform-access-matrix SSO-gate wave). Pipes
# bind-app-group.py into `ak shell`.
#
# Usage:   scripts/authentik/bind-app-group.sh <app-slug> <group-name>
# Example: scripts/authentik/bind-app-group.sh grafana ktayl-engineering
#
# Requires: kubectl context with access to the `authentik` namespace. Run on the controller.
set -euo pipefail
SLUG="${1:?app-slug required}"; GROUP="${2:?group name required}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

kubectl exec -i -n authentik "$POD" -- \
  env AK_APP_SLUG="$SLUG" AK_GROUP="$GROUP" \
  ak shell < "$HERE/bind-app-group.py"
