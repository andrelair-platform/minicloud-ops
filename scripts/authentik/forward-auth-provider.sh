#!/usr/bin/env bash
# Create (idempotently) an Authentik **forward-auth** (proxy) provider + application for an app that has
# NO native OIDC — gated to a group + attached to the embedded outpost — by piping forward-auth-provider.py
# into `ak shell` in the authentik server pod. The one-command runner for forward-auth onboarding (the
# counterpart to oidc-provider.sh; the forward-auth .py previously had no wrapper).
#
# Usage:   scripts/authentik/forward-auth-provider.sh <slug> <host> [<group>]
# Example: scripts/authentik/forward-auth-provider.sh adminer adminer.10.0.0.200.nip.io "Platform Admins"
#   <slug>  — the app slug (provider is named "<slug>-forward-auth", application slug is "<slug>").
#   <host>  — the app host; bare (adminer.10.0.0.200.nip.io) or full (https://…). https:// is prepended.
#   <group> — the Authentik group allowed in (default "Platform Admins"); MUST already exist —
#             run  scripts/authentik/ensure-groups.sh "<group>"  first.
#
# Pair it with the matching ingress forward-auth annotations on the app (the Backstage wrapper-service
# template scaffolds them when needsSSO=true). Requires a kubectl context with access to the `authentik`
# namespace. Run on the controller.
set -euo pipefail
SLUG="${1:?slug required}"; HOST="${2:?host required}"; GROUP="${3:-Platform Admins}"
case "$HOST" in https://*) ;; *) HOST="https://$HOST" ;; esac
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD=$(kubectl get pod -n authentik -l app.kubernetes.io/component=server \
        -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod found" >&2; exit 1; }

# forward-auth-provider.py reads its parameters from globals() (globals().get("NAME", …)), NOT env —
# so prepend the Python assignments to the piped script (its documented interface). Slugs/hosts/group
# names carry no single quotes, so single-quoted Python literals are safe.
{ echo "NAME='${SLUG}-forward-auth'; SLUG='${SLUG}'; HOST='${HOST}'; GROUP='${GROUP}'"
  cat "$HERE/forward-auth-provider.py"
} | kubectl exec -i -n authentik "$POD" -- ak shell
