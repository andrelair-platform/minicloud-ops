"""
Auto-remediation actions that run BEFORE the health checks.

Pattern: detect → diagnose → remediate → log.
Never blindly restarts a service; always checks preconditions first.
"""
import subprocess
import time
from datetime import datetime, timezone


def _log(path: str, msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with open(path, "a") as fh:
            fh.write(f"{ts} {msg}\n")
    except OSError:
        pass


def _docker_state(container: str) -> str:
    try:
        r = subprocess.run(
            ["docker", "inspect", container, "--format", "{{.State.Status}}"],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"


def _disk_pct(path: str = "/") -> int:
    try:
        r = subprocess.run(
            ["df", path, "--output=pcent"],
            capture_output=True, text=True, timeout=5,
        )
        return int(r.stdout.strip().splitlines()[-1].strip().rstrip("%"))
    except Exception:
        return 100  # assume full when we can't check


def remediate_minio(log_path: str, disk_threshold_pct: int = 90) -> None:
    state = _docker_state("minio")
    if state == "running":
        return
    pct = _disk_pct()
    if pct < disk_threshold_pct:
        subprocess.run(["docker", "restart", "minio"], capture_output=True, timeout=30)
        time.sleep(10)
        _log(log_path, f"MinIO restarted (disk {pct}%, was {state})")
    else:
        _log(log_path, f"MinIO stopped: disk {pct}% >= {disk_threshold_pct}% — NOT restarting")


def remediate_cloudflared(log_path: str) -> None:
    try:
        rc = subprocess.run(
            ["systemctl", "is-active", "cloudflared"],
            capture_output=True, timeout=5,
        ).returncode
    except Exception:
        return
    if rc == 0:
        return
    subprocess.run(["systemctl", "restart", "cloudflared"], capture_output=True, timeout=15)
    time.sleep(5)
    _log(log_path, "cloudflared restarted")
