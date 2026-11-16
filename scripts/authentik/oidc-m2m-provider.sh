#!/usr/bin/env bash
# Create (idempotently) an Authentik OAuth2 **M2M / client-credentials** provider + application, by
# piping oidc-m2m-provider.py into `ak shell` in the authentik server pod. Prints CLIENTID=/CLIENTSECRET=/
# ISSUER= markers on stdout — the CALLER captures them and writes the creds to Vault (never echo elsewhere).
#
# Usage:  scripts/authentik/oidc-m2m-provider.sh <slug> <display-name>
# Example: scripts/authentik/oidc-m2m-provider.sh dms-classifier "DMS Classifier (M2M)"
#
# Then (manually, break-glass root): write CLIENTID/CLIENTSECRET to Vault secret/platform/<slug>
#   (oidc-client-id / oidc-client-secret) and confirm the consumer's trusted-issuer allowlist includes
#   the printed ISSUER. See .claude/rules (M2M wiring) + the dms-classifier chart (externalsecret-oidc.yaml).
#
# Requires: kubectl context with access to the `authentik` namespace. Run on the controller.
set -euo pipefail
SLUG="${1:?slug required}"; NAME="${2:?display-name required}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

kubectl exec -i -n authentik "$POD" -- \
  env AK_APP_SLUG="$SLUG" AK_APP_NAME="$NAME" AK_ISSUER_MODE=per_provider \
  ak shell < "$HERE/oidc-m2m-provider.py"
