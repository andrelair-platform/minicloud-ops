#!/usr/bin/env bash
# Update the redirect_uris of an existing Authentik OAuth2 provider, by piping
# set-provider-redirect.py into `ak shell` in the authentik server pod.
#
# Usage:  scripts/authentik/set-provider-redirect.sh <slug> <redirect-uri>[,<uri>...] [strict|regex]
# Example (GLPI appends /provider/<id> → needs a regex):
#   scripts/authentik/set-provider-redirect.sh glpi \
#     'https://itsm\.devandre\.sbs/plugins/singlesignon/front/callback\.php.*' regex
#
# Requires: kubectl context with access to the `authentik` namespace. Run on the controller.
set -euo pipefail
SLUG="${1:?slug required}"; REDIRECTS="${2:?redirect-uri(s) required}"; MODE="${3:-strict}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

# kubectl exec has no --env flag → set the vars with `env` inside the container, before `ak shell`.
kubectl exec -i -n authentik "$POD" -- \
  env AK_PROVIDER_SLUG="$SLUG" AK_REDIRECT_URIS="$REDIRECTS" AK_MATCH_MODE="$MODE" \
  ak shell < "$HERE/set-provider-redirect.py"
