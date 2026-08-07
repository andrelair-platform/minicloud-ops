#!/usr/bin/env python3
"""
Send WoL magic packet to swift-mac (a8:20:66:2e:d9:71) when the node
is NotReady in k3s. Intended to run once at boot via systemd service
(minicloud-wake-swift-mac.service) and every 5 minutes via cron as retry.
Exits 0 silently if swift-mac is Ready; sends magic packet and exits 0 if NotReady.
"""
import socket
import subprocess
import sys

MAC = "a8:20:66:2e:d9:71"
BROADCAST = "10.0.0.255"
PORT = 9


def node_ready(node: str) -> bool:
    try:
        out = subprocess.check_output(
            ["kubectl", "get", "node", node, "-o",
             "jsonpath={.status.conditions[?(@.type=='Ready')].status}"],
            timeout=10, text=True,
        )
        return out.strip() == "True"
    except Exception:
        return False


def send_magic_packet(mac: str, broadcast: str, port: int) -> None:
    raw = mac.replace(":", "")
    payload = bytes.fromhex("F" * 12 + raw * 16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(payload, (broadcast, port))


if node_ready("swift-mac"):
    sys.exit(0)

print("swift-mac NotReady — sending WoL magic packet")
send_magic_packet(MAC, BROADCAST, PORT)
