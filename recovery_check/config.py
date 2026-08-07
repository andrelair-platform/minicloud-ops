# ──────────────────────────────────────────────────────────────────────────────
# minicloud-ops · recovery_check · config.py
#
# Edit this file to customise thresholds, URLs, and notification targets.
# Then re-run `sudo pip3 install --break-system-packages -e .` on the controller
# to pick up the changes (no service restart needed, re-read at every run).
# ──────────────────────────────────────────────────────────────────────────────

# Set to a real healthchecks.io UUID to receive failure reports via POST.
# Example: "https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/fail"
HC_FAIL_URL: str = "https://hc-ping.com/REPLACE_WITH_UUID/fail"

# Log destinations (must be writable by the user running the service)
LOG_FILE: str = "/var/log/minicloud-recovery.log"
RTO_LOG: str = "/var/log/minicloud-rto.log"
REMEDIATION_LOG: str = "/var/log/minicloud-remediation.log"

# ── Connectivity targets ───────────────────────────────────────────────────────
INTERNET_CHECK_URL: str = "https://1.1.1.1"
VAULT_HEALTH_URL: str = "https://vault.devandre.sbs/v1/sys/health"
PUBLIC_CHECK_URL: str = "https://homer.devandre.sbs"

# ── Kubernetes ────────────────────────────────────────────────────────────────
EXPECTED_NODE_COUNT: int = 5

# (namespace, pod_name) pairs – checked with pg_isready
POSTGRES_INSTANCES: list[tuple[str, str]] = [
    ("ai", "postgresql-ai-0"),
    ("chat", "postgresql-synapse-0"),
]

# ── Remediation ───────────────────────────────────────────────────────────────
# MinIO is NOT restarted if controller disk usage is above this threshold
MINIO_DISK_RESTART_THRESHOLD_PCT: int = 90
