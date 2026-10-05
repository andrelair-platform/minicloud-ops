#!/usr/bin/env bash
# Create the `Workplace Users` birthright group + bind the birthright workplace apps.
# Pipes workplace-birthright.py into `ak shell` inside the authentik-server pod (REST API 403s on
# 2026.5.3 → ORM). Idempotent + re-runnable. See the .py header for the model + safety notes.
# RUN ON THE CONTROLLER. Env WP_GROUP / WP_APPS optional (see the .py defaults).
set -euo pipefail
NS="${AK_NS:-authentik}"
POD=$(kubectl get pod -n "$NS" -l app.kubernetes.io/component=server -o jsonpath='{.items[0].metadata.name}')
[ -n "$POD" ] || { echo "ERROR: no authentik server pod in ns $NS" >&2; exit 1; }
DIR="$(cd "$(dirname "$0")" && pwd)"
kubectl exec -i -n "$NS" "$POD" -- env \
  WP_GROUP="${WP_GROUP:-Workplace Users}" WP_APPS="${WP_APPS:-}" \
  ak shell < "$DIR/workplace-birthright.py"
