#!/usr/bin/env bash
# Provision (idempotently) an Authentik directory user — the single source of truth for identity, so
# downstream apps (ERPNext, …) map to it via SSO instead of inventing local accounts. Pipes
# create-directory-user.py into `ak shell`. SSO-only (no password). Manual stand-in for the ktayl-iam
# v3 Joiner→Authentik provisioning.
#
# Usage:  scripts/authentik/create-directory-user.sh <username> <email> [display-name] [group]
# Example: scripts/authentik/create-directory-user.sh 100002 100002@ktayl.local "Marie Leclerc"
#
# Requires: kubectl context with access to the `authentik` namespace. Run on the controller.
set -euo pipefail
USERNAME="${1:?username required}"; EMAIL="${2:?email required}"; NAME="${3:-}"; GROUP="${4:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

kubectl exec -i -n authentik "$POD" -- \
  env AK_USERNAME="$USERNAME" AK_EMAIL="$EMAIL" ${NAME:+AK_NAME="$NAME"} ${GROUP:+AK_GROUP="$GROUP"} \
  ak shell < "$HERE/create-directory-user.py"
