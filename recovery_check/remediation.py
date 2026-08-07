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


def remediate_k3s_backup(
    log_path: str,
    backup_script: str = "/home/ktayl/bin/kine-backup.sh",
) -> None:
    """Trigger an emergency k3s backup in the background (only call when backup is confirmed stale)."""
    import os
    try:
        # kine-backup.sh uses mc under ~ktayl — HOME ensures the alias is found when running as root
        env = {**os.environ, "HOME": "/home/ktayl"}
        subprocess.Popen(
            [backup_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        _log(log_path, f"k3s emergency backup triggered ({backup_script})")
    except Exception as exc:
        _log(log_path, f"k3s backup trigger failed: {exc}")


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
