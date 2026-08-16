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



_MINIO_DISK_FLAG = "/home/ktayl/.minicloud/minio-was-full.flag"


def remediate_minio_disk_recovery(log_path: str, high_pct: int = 90, low_pct: int = 80) -> None:
    """Restart MinIO after disk recovers from a full event (clears cached disk-full error).

    MinIO caches the disk-full state in memory; after disk space is freed the
    container keeps refusing writes until restarted.  This function tracks the
    high-water mark via a flag file in /var/run (tmpfs → cleared on reboot) and
    issues 'docker restart minio' exactly once when the disk drops below the low
    threshold after having been above the high threshold.
    """
    from pathlib import Path
    pct = _disk_pct()
    flag = Path(_MINIO_DISK_FLAG)

    if pct >= high_pct:
        flag.touch(exist_ok=True)
        return

    if pct < low_pct and flag.exists():
        if _docker_state("minio") == "running":
            subprocess.run(["docker", "restart", "minio"], capture_output=True, timeout=30)
            time.sleep(10)
            _log(log_path, f"MinIO restarted after disk recovery ({pct}% < {low_pct}%)")
        flag.unlink(missing_ok=True)
