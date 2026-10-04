"""
Entry point for the minicloud recovery check.

Usage:
    minicloud-recovery-check          # installed entry point
    python3 -m recovery_check.main    # from repo root
"""
import subprocess
import sys
import time
from datetime import datetime, timezone

from . import config
from .checks import (
    check_argocd_apps,
    check_authentik,
    check_cert_manager,
    check_cloudflared,
    check_controller_disk,
    check_dns,
    check_harbor,
    check_http_app,
    check_ingress_nginx,
    check_internet,
    check_k3s_backup_age,
    check_k3s_nodes,
    check_litellm,
    check_longhorn_instance_managers,
    check_longhorn_volumes,
    check_minio_docker,
    check_monitoring,
    check_node_resources,
    check_mount_writable,
    check_postgres,
    check_public_endpoint,
    check_pvcs,
    check_tailscale,
    check_upstream_dns,
    check_vault,
)
from .models import CheckResult
from .remediation import remediate_k3s_backup, remediate_minio, remediate_minio_disk_recovery


def _boot_timestamp() -> int:
    """Return Unix timestamp of last system boot."""
    try:
        out = subprocess.run(
            ["uptime", "-s"], capture_output=True, text=True
        ).stdout.strip()
        dt = datetime.strptime(out, "%Y-%m-%d %H:%M:%S")
        return int(dt.timestamp())
    except Exception:
        return int(time.time())


def _append(path: str, text: str) -> None:
    try:
        with open(path, "a") as fh:
            fh.write(text + "\n")
    except OSError:
        pass


def _notify_failure(report: str) -> None:
    if "REPLACE_WITH_UUID" in config.HC_FAIL_URL:
        return
    subprocess.run(
        ["curl", "-fsS", "--max-time", "10", "--data-raw", report, config.HC_FAIL_URL],
        capture_output=True,
    )


def _notify_success(report: str) -> None:
    # Ping the SUCCESS endpoint (base URL, no /fail) so the healthchecks.io check
    # goes GREEN when the platform is healthy. Without this a healthy run pinged
    # nothing -> the check could only ever go stale/red.
    if "REPLACE_WITH_UUID" in config.HC_FAIL_URL:
        return
    url = config.HC_FAIL_URL.rsplit("/fail", 1)[0]
    subprocess.run(
        ["curl", "-fsS", "--max-time", "10", "--data-raw", report, url],
        capture_output=True,
    )


def main() -> int:
    boot_ts = _boot_timestamp()
    start_ts = int(time.time())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Auto-remediation before checks ────────────────────────────────────────
    remediate_minio(config.REMEDIATION_LOG, config.MINIO_DISK_RESTART_THRESHOLD_PCT)
    remediate_minio_disk_recovery(config.REMEDIATION_LOG)

    # ── Run all checks ────────────────────────────────────────────────────────
    results: list[CheckResult] = []

    results.append(check_internet(config.INTERNET_CHECK_URL))
    results.append(check_dns())
    results.append(check_upstream_dns(config.UPSTREAM_DNS_SERVER, config.UPSTREAM_DNS_TEST_DOMAIN))
    results.append(check_k3s_nodes(config.EXPECTED_NODE_COUNT))
    results.append(check_node_resources(config.NODE_MEM_PCT_THRESHOLD))
    results.append(check_longhorn_volumes())
    results.append(check_longhorn_instance_managers(config.LONGHORN_MIN_SCHEDULABLE_NODES))
    results.append(check_pvcs())
    for _label, _ns, _tgt, _path in config.MOUNT_WRITABLE_PROBES:
        results.append(check_mount_writable(_label, _ns, _tgt, _path))
    results.append(check_argocd_apps())
    for ns, pod in config.POSTGRES_INSTANCES:
        results.append(check_postgres(ns, pod))
    results.append(check_vault(config.VAULT_HEALTH_URL))
    results.append(check_authentik(config.AUTHENTIK_HEALTH_URL))
    results.append(check_ingress_nginx(config.INGRESS_NGINX_NAMESPACE, config.INGRESS_NGINX_DEPLOYMENT))
    results.append(check_cert_manager(config.CERT_EXPIRY_WARN_DAYS))
    results.append(check_harbor())
    results.append(check_minio_docker())
    results.append(check_controller_disk(config.CONTROLLER_DISK_PCT_THRESHOLD))
    results.append(check_monitoring())
    results.append(check_litellm(config.LITELLM_HEALTH_URL))
    results.append(check_cloudflared())
    results.append(check_tailscale())
    results.append(check_public_endpoint(config.PUBLIC_CHECK_URL))
    for _label, _host, _path, _rip in config.FLAGSHIP_PROBES:
        results.append(check_http_app(_label, _host, _path, _rip))
    backup_result = check_k3s_backup_age(
        mc_path=config.MC_PATH,
        bucket=config.K3S_BACKUP_BUCKET,
        max_age_hours=config.K3S_BACKUP_MAX_AGE_HOURS,
    )
    results.append(backup_result)

    # ── Build report ──────────────────────────────────────────────────────────
    end_ts = int(time.time())
    uptime_at_start = start_ts - boot_ts
    platform_ready = end_ts - boot_ts

    passed = sum(1 for r in results if r.ok)
    failed = sum(1 for r in results if not r.ok)
    status = "HEALTHY" if failed == 0 else f"DEGRADED ({failed} failed)"

    check_lines = "\n".join(str(r) for r in results)
    report = (
        f"====================================\n"
        f" MINICLOUD RECOVERY REPORT\n"
        f" {now}  uptime: {uptime_at_start}s\n"
        f"====================================\n"
        f"{check_lines}\n"
        f"------------------------------------\n"
        f" platform_ready_in: {platform_ready}s\n"
        f" STATUS: {status}\n"
        f"===================================="
    )

    print(report)
    _append(config.LOG_FILE, report)
    _append(
        config.RTO_LOG,
        f"{now}  uptime_at_start={uptime_at_start}s  "
        f"platform_ready={platform_ready}s  passed={passed}  failed={failed}  status={status}",
    )

    if failed > 0:
        _notify_failure(report)
    else:
        _notify_success(report)
        if not backup_result.ok:
            # Platform is otherwise healthy — safe to trigger an emergency backup
            remediate_k3s_backup(config.REMEDIATION_LOG, config.K3S_BACKUP_SCRIPT)

    return failed


if __name__ == "__main__":
    sys.exit(main())
