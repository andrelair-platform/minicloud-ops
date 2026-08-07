#!/bin/bash
# Install minicloud-ops tooling on the controller.
# Run once from the cloned repo: sudo bash install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR=/etc/systemd/system

echo "=== Symlinking package (no pip needed) ==="
mkdir -p /usr/local/lib/minicloud
ln -sfn "$REPO_DIR/recovery_check" /usr/local/lib/minicloud/recovery_check

echo "=== Creating entry point ==="
cat > /usr/local/bin/minicloud-recovery-check << 'ENTRY'
#!/bin/bash
# git pull in ~/minicloud-ops picks up changes immediately via the symlink
export PYTHONPATH="/usr/local/lib/minicloud${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m recovery_check.main "$@"
ENTRY
chmod +x /usr/local/bin/minicloud-recovery-check
echo "Entry point: /usr/local/bin/minicloud-recovery-check"

echo "=== Creating log files (world-writable so ktayl and root can both append) ==="
for f in /var/log/minicloud-recovery.log /var/log/minicloud-rto.log /var/log/minicloud-remediation.log /var/log/minicloud-wol.log; do
    touch "$f"
    chmod 666 "$f"
done

echo "=== Installing heartbeat config (edit UUID before enabling timer) ==="
mkdir -p /etc/minicloud
if [ ! -f /etc/minicloud/heartbeat.env ]; then
    cat > /etc/minicloud/heartbeat.env << 'ENV'
# Replace with your healthchecks.io check URL (period=2min, grace=10min)
HC_HEARTBEAT_URL=https://hc-ping.com/REPLACE_WITH_UUID
ENV
    echo "Created /etc/minicloud/heartbeat.env — set HC_HEARTBEAT_URL before enabling the timer"
else
    echo "/etc/minicloud/heartbeat.env already exists — leaving unchanged"
fi

echo "=== Installing swift-mac WoL script ==="
install -m 755 "$REPO_DIR/scripts/swift-mac-wake.py" /usr/local/bin/minicloud-wake-swift-mac

echo "=== Installing systemd services ==="
cp "$REPO_DIR/systemd/minicloud-post-boot-check.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/restore-cluster-nat.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-heartbeat.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-heartbeat.timer" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-wake-swift-mac.service" "$SYSTEMD_DIR/"

systemctl daemon-reload
systemctl enable minicloud-post-boot-check.service
systemctl enable restore-cluster-nat.service
systemctl enable minicloud-wake-swift-mac.service
# Timer is NOT enabled automatically — operator must set UUID first:
#   edit /etc/minicloud/heartbeat.env
#   systemctl enable --now minicloud-heartbeat.timer

echo ""
echo "=== Done ==="
echo "Manual check:   minicloud-recovery-check"
echo "Logs:           /var/log/minicloud-recovery.log"
echo "                /var/log/minicloud-rto.log"
echo "                /var/log/minicloud-remediation.log"
echo ""
echo "=== To enable heartbeat (after setting UUID in /etc/minicloud/heartbeat.env): ==="
echo "  systemctl enable --now minicloud-heartbeat.timer"
echo "  systemctl list-timers minicloud-heartbeat.timer"
