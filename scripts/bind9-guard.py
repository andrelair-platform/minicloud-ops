#!/usr/bin/env python3
"""
Ensure the MAAS-managed bind9 service (cluster DNS on 10.0.0.1:53) is running
at boot.

After a controller disk-full / unclean crash, MAAS can leave bind9 in its
pebble plan as startup=disabled / Current=inactive, and regiond does not always
re-enable it on the next restart. When bind9 is down, `named` is gone, so the
k3s cluster's CoreDNS (which forwards external queries to 10.0.0.1) can no
longer resolve anything off-cluster -> the Alertmanager watchdog webhook to
hc-ping.com fails -> healthchecks.io marks the platform DOWN. The cluster core
stays up; only external name resolution breaks.

Runs once at boot via minicloud-bind9-guard.service (after snap.maas.pebble),
mirroring the WoL / NAT post-boot guards. Idempotent: exits 0 if bind9 is
already active; starts it and exits 0 if it was down. Must run as root -- the
pebble control socket under /var/snap/maas/common/pebble is root-owned.

See: 2026-08-18 disk-full -> cluster DNS outage post-mortem.
"""
import os
import subprocess
import sys

PEBBLE_DIR = "/var/snap/maas/common/pebble"
PEBBLE_BIN = "/snap/maas/current/bin/pebble"  # 'current' symlink survives upgrades
SERVICE = "bind9"


def pebble(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PEBBLE": PEBBLE_DIR}
    return subprocess.run(
        [PEBBLE_BIN, *args],
        env=env, capture_output=True, text=True, timeout=30,
    )


def bind9_active() -> bool:
    """Parse `pebble services bind9`. Columns: Service Startup Current Since."""
    try:
        r = pebble("services", SERVICE)
    except Exception as exc:  # pebble socket not up yet, binary missing, etc.
        print(f"cannot query pebble ({exc}) -- assuming bind9 down")
        return False
    for line in r.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == SERVICE:
            return "active" in parts  # exact-token match; 'inactive' != 'active'
    return False


def main() -> int:
    if bind9_active():
        print(f"{SERVICE} already active -- nothing to do")
        return 0
    print(f"{SERVICE} not active -- starting via pebble")
    try:
        r = pebble("start", SERVICE)
    except Exception as exc:
        print(f"pebble start {SERVICE} raised: {exc}")
        return 0  # never fail the unit; this is a best-effort guard
    if r.returncode != 0:
        print(f"pebble start {SERVICE} failed: {r.stderr.strip()}")
        return 0
    state = "active" if bind9_active() else "still not active (check pebble logs bind9)"
    print(f"pebble start {SERVICE}: ok -> {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
