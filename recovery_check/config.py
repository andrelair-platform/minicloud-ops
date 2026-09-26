# ──────────────────────────────────────────────────────────────────────────────
# minicloud-ops · recovery_check · config.py
#
# Edit this file to customise thresholds, URLs, and notification targets.
# Then re-run `sudo pip3 install --break-system-packages -e .` on the controller
# to pick up the changes (no service restart needed, re-read at every run).
# ──────────────────────────────────────────────────────────────────────────────

# Set to a real healthchecks.io UUID to receive failure reports via POST.
# Example: "https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/fail"
HC_FAIL_URL: str = "https://hc-ping.com/6a37bfa6-3633-4f3c-afbb-8b76ba4f508e/fail"

# Log destinations (must be writable by the user running the service)
LOG_FILE: str = "/var/log/minicloud-recovery.log"
RTO_LOG: str = "/var/log/minicloud-rto.log"
REMEDIATION_LOG: str = "/var/log/minicloud-remediation.log"

# ── Connectivity targets ───────────────────────────────────────────────────────
INTERNET_CHECK_URL: str = "https://1.1.1.1"
# Use the INTERNAL ingress URL, not the public devandre.sbs one: the Cloudflare tunnel
# returns 404 for Vault's /v1/sys/health API path, which the old check misread as
# "unreachable" (2026-09-26 false-flag — Vault was healthy all along). The internal URL
# serves the real health JSON. standbyok/perfstandbyok also make an unsealed HA standby
# report 200; the check judges health from the JSON body (initialized + not sealed) anyway.
VAULT_HEALTH_URL: str = "https://vault.10.0.0.200.nip.io/v1/sys/health?standbyok=true&perfstandbyok=true"
PUBLIC_CHECK_URL: str = "https://homer.devandre.sbs"

# Authentik SSO — the identity perimeter (every app is behind it). Health endpoint
# probed through the public ingress (exercises ingress + authentik together).
AUTHENTIK_HEALTH_URL: str = "https://auth.devandre.sbs/-/health/ready/"

# Controller MAAS bind9 upstream. CoreDNS forwards external queries here;
# if bind9 (10.0.0.1:53) is down the whole cluster loses external DNS while
# check_dns() still passes (kubernetes.default resolves internally).
# 2026-08-18 disk-full -> DNS outage post-mortem.
UPSTREAM_DNS_SERVER: str = "10.0.0.1"
UPSTREAM_DNS_TEST_DOMAIN: str = "hc-ping.com"

# ── Kubernetes ────────────────────────────────────────────────────────────────
EXPECTED_NODE_COUNT: int = 5

# Fail the node-resources check if any node reports a kubelet *Pressure condition
# (Memory/Disk/PID) OR its memory usage exceeds this percent. 2026-09-26: fast-heron
# at 89% mem stalled Longhorn rebuilds and cascaded — this would have flagged it early.
NODE_MEM_PCT_THRESHOLD: int = 92

# ingress-nginx controller — one Degraded controller = all *.nip.io + public ingress down.
INGRESS_NGINX_NAMESPACE: str = "ingress-nginx"
INGRESS_NGINX_DEPLOYMENT: str = "nginx-ingress-ingress-nginx-controller"

# Longhorn RF-3 headroom: fail if fewer than this many Longhorn nodes are schedulable
# (too few replica homes = the stuck-rebuild situation from the 2026-09-26 incident).
LONGHORN_MIN_SCHEDULABLE_NODES: int = 3

# (namespace, pod_name) pairs – checked with pg_isready
POSTGRES_INSTANCES: list[tuple[str, str]] = [
    ("ai", "postgresql-ai-0"),
    ("chat", "postgresql-synapse-0"),
]

# ── Remediation ───────────────────────────────────────────────────────────────
# MinIO is NOT restarted if controller disk usage is above this threshold
MINIO_DISK_RESTART_THRESHOLD_PCT: int = 90

# ── k3s backup ────────────────────────────────────────────────────────────────
MC_PATH: str = "/home/ktayl/.local/bin/mc"
K3S_BACKUP_BUCKET: str = "minilocal/k3s-backup/"
K3S_BACKUP_MAX_AGE_HOURS: int = 25
K3S_BACKUP_SCRIPT: str = "/home/ktayl/bin/kine-backup.sh"
