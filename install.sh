#!/bin/bash
# Install minicloud-ops tooling on the controller.
# Run once from the cloned repo: sudo bash install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR=/etc/systemd/system

echo "=== Installing Python package ==="
pip3 install --break-system-packages -e "$REPO_DIR" --quiet
echo "Entry point: $(which minicloud-recovery-check)"

echo "=== Installing systemd services ==="
cp "$REPO_DIR/systemd/minicloud-post-boot-check.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/restore-cluster-nat.service" "$SYSTEMD_DIR/"

systemctl daemon-reload
systemctl enable minicloud-post-boot-check.service
systemctl enable restore-cluster-nat.service

echo ""
echo "=== Done. To run a manual check now: ==="
echo "  minicloud-recovery-check"
echo ""
echo "=== Logs will be written to: ==="
echo "  /var/log/minicloud-recovery.log"
echo "  /var/log/minicloud-rto.log"
echo "  /var/log/minicloud-remediation.log"
