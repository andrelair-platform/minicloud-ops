#!/bin/bash
# Post-power-on cluster settle + verify. Run from the controller AFTER powering
# machines on in order: controller (30s) -> set-hog (2min) -> workers.
# k3s / k3s-agent auto-start on boot; this waits for the API, shows health,
# and uncordons the workers the shutdown script cordoned.
set -uo pipefail
WORKER_NAMES="fast-skunk fast-heron star-kitten loving-gannet swift-mac"

echo "[1/4] Waiting for the k3s API..."
for i in $(seq 1 60); do kubectl get --raw=/healthz >/dev/null 2>&1 && break; sleep 5; done
kubectl get --raw=/healthz >/dev/null 2>&1 && echo "  API up" || { echo "  API still down after 5min — check set-hog"; exit 1; }

echo "[2/4] Nodes:"; kubectl get nodes 2>/dev/null | sed 's/^/  /'

echo "[3/4] Uncordoning workers..."
for n in $WORKER_NAMES; do kubectl uncordon "$n" 2>/dev/null && echo "  uncordoned $n"; done

echo "[4/4] Longhorn will re-sync any stale replicas over the next while:"
echo "  watch: kubectl get volumes.longhorn.io -n longhorn-system -o custom-columns=NAME:.metadata.name,STATE:.status.state,HEALTH:.status.robustness"
echo "Done."
