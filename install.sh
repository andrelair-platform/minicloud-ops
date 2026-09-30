#!/bin/bash
# Install minicloud-ops tooling on the controller.
# Run once from the cloned repo: sudo bash install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR=/etc/systemd/system

echo "=== Symlinking package (no pip needed) ==="
mkdir -p /usr/local/lib/minicloud
ln -sfn "$REPO_DIR/recovery_check" /usr/local/lib/minicloud/recovery_check
ln -sfn "$REPO_DIR/sdlc_loop" /usr/local/lib/minicloud/sdlc_loop

echo "=== Creating entry point ==="
cat > /usr/local/bin/minicloud-recovery-check << 'ENTRY'
#!/bin/bash
# git pull in ~/minicloud-ops picks up changes immediately via the symlink
export PYTHONPATH="/usr/local/lib/minicloud${PYTHONPATH:+:$PYTHONPATH}"
# Ensure kubectl works for any invocation (manual, timer), not just the unit env
export KUBECONFIG="${KUBECONFIG:-/home/ktayl/.kube/config}"
exec python3 -m recovery_check.main "$@"
ENTRY
chmod +x /usr/local/bin/minicloud-recovery-check
echo "Entry point: /usr/local/bin/minicloud-recovery-check"

cat > /usr/local/bin/minicloud-sdlc-loop << 'ENTRY'
#!/bin/bash
# SDLC closing-the-loop detector (Play 13). git pull picks up changes via the symlink.
export PYTHONPATH="/usr/local/lib/minicloud${PYTHONPATH:+:$PYTHONPATH}"
export KUBECONFIG="${KUBECONFIG:-/home/ktayl/.kube/config}"
exec python3 -m sdlc_loop.main "$@"
ENTRY
chmod +x /usr/local/bin/minicloud-sdlc-loop
echo "Entry point: /usr/local/bin/minicloud-sdlc-loop"

echo "=== Creating log files (world-writable so ktayl and root can both append) ==="
for f in /var/log/minicloud-recovery.log /var/log/minicloud-rto.log /var/log/minicloud-remediation.log /var/log/minicloud-wol.log; do
    touch "$f"
    chmod 666 "$f"
done

echo "=== Creating state directory for ktayl user ==="
mkdir -p /home/ktayl/.minicloud
touch /home/ktayl/.minicloud/minio-was-full.flag
chown ktayl:ktayl /home/ktayl/.minicloud /home/ktayl/.minicloud/minio-was-full.flag

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
install -m 755 "$REPO_DIR/scripts/maas-power-broker.py" /usr/local/bin/maas-power-broker
install -m 755 "$REPO_DIR/scripts/bind9-guard.py" /usr/local/bin/minicloud-bind9-guard

echo "=== Installing systemd services ==="
cp "$REPO_DIR/systemd/minicloud-post-boot-check.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-recovery-check.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-recovery-check.timer" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/restore-cluster-nat.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-heartbeat.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-heartbeat.timer" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-wake-swift-mac.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/maas-power-broker.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-bind9-guard.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-bind9-guard.timer" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-sdlc-loop.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/systemd/minicloud-sdlc-loop.timer" "$SYSTEMD_DIR/"

systemctl daemon-reload
systemctl enable minicloud-post-boot-check.service
systemctl enable --now minicloud-recovery-check.timer
systemctl enable restore-cluster-nat.service
systemctl enable minicloud-wake-swift-mac.service
systemctl enable --now maas-power-broker.service
systemctl enable --now minicloud-bind9-guard.timer
systemctl enable --now minicloud-sdlc-loop.timer
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
echo ""
echo "=== SDLC closing-the-loop detector (Play 13) ==="
echo "  Runs hourly; logs to journald; writes intents to ~/minicloud-ops-intents/."
echo "  Verify:   minicloud-sdlc-loop --dry-run   (never opens issues)"
echo "  Journal:  journalctl -u minicloud-sdlc-loop.service --no-pager | tail"
echo "  Tier-3 (3sigma) opens a GitHub issue ONLY if a scoped token is present:"
echo "    echo '<fine-grained PAT, issues:write on minicloud-gitops>' > ~/.sdlc-loop-github-token"
echo "    chmod 600 ~/.sdlc-loop-github-token"
echo "  Without the token the loop still logs + writes intent.md (issue step is skipped)."
