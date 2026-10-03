#!/usr/bin/env bash
# Toggle GLOBAL MFA enforcement in Authentik (the Authenticator Validation stage in the shared
# authentication flow). Reversible — only flips FlowStageBinding.enabled, never deletes TOTP devices.
#
# Usage:  scripts/authentik/mfa-toggle.sh on|off
#   off  -> login is username+password only (MFA skipped) for ALL SSO apps
#   on   -> re-enforce MFA for ALL SSO apps
#
# Requires: kubectl with access to the `authentik` namespace. Run on the controller.
set -euo pipefail
case "${1:-}" in
  on)  MFA=true ;;
  off) MFA=false ;;
  *)   echo "usage: $0 on|off" >&2; exit 1 ;;
esac
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

kubectl exec -i -n authentik "$POD" -- env MFA_ENABLED="$MFA" ak shell < "$HERE/mfa-toggle.py"
