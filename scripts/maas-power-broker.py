#!/usr/bin/env python3
"""MAAS webhook power broker for bare-metal ThinkPad nodes.
Listens on 127.0.0.1:5241.

Query uses ping (fast, 1s timeout). Power off/reset use SSH.
Power on sends Wake-on-LAN magic packet via broadcast.

MAAS webhook regex defaults:
  power_on_regex:  status.*:.*running  → matched by {"status": "running"}
  power_off_regex: status.*:.*stopped  → matched by {"status": "stopped"}
"""

import json
import socket
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

NODES = {
    "set-hog":     {"mac": "38:f3:ab:92:35:3f", "ip": "10.0.0.2", "user": "ubuntu"},
    "fast-skunk":  {"mac": "f8:75:a4:dd:dc:59", "ip": "10.0.0.4", "user": "ubuntu"},
    "fast-heron":  {"mac": "f8:75:a4:dd:e5:2d", "ip": "10.0.0.7", "user": "ubuntu"},
    "star-kitten": {"mac": "f8:75:a4:f9:2f:e9", "ip": "10.0.0.8", "user": "ubuntu"},
    "loving-gannet": {"mac": "f8:75:a4:fd:91:cb", "ip": "10.0.0.9", "user": "ubuntu"},
}

WOL_BROADCAST = "10.0.0.255"
SSH_OPTS = [
    "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
    "-o", "BatchMode=yes", "-o", "LogLevel=error",
]


def send_wol(mac: str) -> None:
    mac_bytes = bytes.fromhex(mac.replace(":", ""))
    packet = b"\xff" * 6 + mac_bytes * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(packet, (WOL_BROADCAST, 9))
        s.sendto(packet, (WOL_BROADCAST, 7))


def ssh_run(ip: str, user: str, cmd: str) -> bool:
    try:
        r = subprocess.run(
            SSH_OPTS + [f"{user}@{ip}", cmd],
            capture_output=True, timeout=20,
        )
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def ping_alive(ip: str) -> bool:
    """Is the host up? ICMP ping first; fall back to ARP-neighbour reachability
    and a TCP:22 probe. The MAAS deploy/ephemeral env often ignores ICMP but is
    clearly on the wire (ARP REACHABLE) and running sshd."""
    try:
        r = subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True, timeout=3)
        if r.returncode == 0:
            return True
    except Exception:
        pass
    # ARP neighbour reachability (works when ICMP is filtered)
    try:
        r = subprocess.run(["ip", "neigh", "show", ip], capture_output=True, timeout=3, text=True)
        if any(st in r.stdout for st in ("REACHABLE", "DELAY", "PROBE")):
            return True
    except Exception:
        pass
    # TCP:22 probe (sshd up in the ephemeral env)
    try:
        with socket.create_connection((ip, 22), timeout=2):
            return True
    except Exception:
        pass
    return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args)

    def send_json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self): self.handle_action()
    def do_GET(self):  self.handle_action()

    def handle_action(self):
        path = urlparse(self.path).path.strip("/").split("/")
        if len(path) != 3 or path[0] != "power":
            self.send_json(404, {"error": "not found"})
            return

        _, action, hostname = path
        node = NODES.get(hostname)
        if not node:
            self.send_json(404, {"error": f"unknown host: {hostname}"})
            return

        ip, user, mac = node["ip"], node["user"], node["mac"]

        if action == "on":
            send_wol(mac)
            self.send_json(200, {"status": "wol-sent", "mac": mac})

        elif action == "off":
            ok = ssh_run(ip, user, "sudo poweroff")
            self.send_json(200, {"status": "stopped" if ok else "error-ssh-failed"})

        elif action == "reset":
            ok = ssh_run(ip, user, "sudo reboot")
            self.send_json(200, {"status": "restarting" if ok else "error-ssh-failed"})

        elif action == "query":
            # Ping is fast (1s) and sufficient for power state detection.
            # Returns MAAS-compatible status strings.
            state = "running" if ping_alive(ip) else "stopped"
            self.send_json(200, {"status": state})

        else:
            self.send_json(400, {"error": f"unknown action: {action}"})


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5241), Handler)
    print("MAAS power broker listening on 0.0.0.0:5241")
    server.serve_forever()
