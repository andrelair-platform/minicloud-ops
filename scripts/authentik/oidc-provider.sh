#!/usr/bin/env bash
# Create (idempotently) an Authentik OIDC provider + application for an app, by piping
# oidc-provider.py into `ak shell` in the authentik server pod. Prints the CLIENTID=/CLIENTSECRET=
# markers on stdout — the CALLER captures them and writes them to Vault (never echo the secret).
#
# Usage:  scripts/authentik/oidc-provider.sh <slug> <display-name> <redirect-uri>[,<redirect-uri>...]
# Example: scripts/authentik/oidc-provider.sh bookstack BookStack https://intranet.devandre.sbs/oidc/callback
#
# Requires: kubectl context with access to the `authentik` namespace. Run on the controller.
set -euo pipefail
SLUG="${1:?slug required}"; NAME="${2:?display-name required}"; REDIRECTS="${3:?redirect-uri(s) required}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

# kubectl exec has no --env flag → set the vars with `env` inside the container, before `ak shell`.
kubectl exec -i -n authentik "$POD" -- \
  env AK_APP_SLUG="$SLUG" AK_APP_NAME="$NAME" AK_REDIRECT_URIS="$REDIRECTS" AK_ADD_GROUPS=1 \
  ak shell < "$HERE/oidc-provider.py"
