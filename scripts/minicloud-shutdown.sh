#!/bin/bash
# Graceful cluster shutdown — run from the controller BEFORE powering anything off.
# The whole point: cleanly stop k3s so kine CHECKPOINTS its SQLite WAL. A clean
# stop = small WAL = fast API on next boot = no rebuild storm. Crash-stopping
# (cutting power) is what caused the 900MB WAL + hours of Longhorn recovery.
set -uo pipefail
SSH="ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 ubuntu@"
WORKERS_IP="10.0.0.4 10.0.0.7 10.0.0.8 10.0.0.9 10.0.0.10"
WORKER_NAMES="fast-skunk fast-heron star-kitten loving-gannet swift-mac"
SERVER_IP="10.0.0.2"   # set-hog (control plane)

echo "[1/3] Cordoning workers (stop new scheduling)..."
for n in $WORKER_NAMES; do kubectl cordon "$n" 2>/dev/null && echo "  cordoned $n"; done

echo "[2/3] Clean-stopping k3s-agent on workers..."
for ip in $WORKERS_IP; do ${SSH}${ip} "sudo systemctl stop k3s-agent" 2>/dev/null && echo "  stopped agent on $ip"; done

echo "[3/3] Clean-stopping k3s on set-hog (this CHECKPOINTS the kine WAL)..."
${SSH}${SERVER_IP} "sudo systemctl stop k3s" 2>/dev/null && echo "  set-hog k3s stopped — WAL checkpointed"

echo ""
echo "SAFE TO POWER OFF NOW. Recommended order: workers -> set-hog -> controller last."
echo "To power the nodes off from here:"
echo "  for ip in $WORKERS_IP $SERVER_IP; do ssh ubuntu@\$ip 'sudo poweroff'; done"
echo "Then power off the controller."
