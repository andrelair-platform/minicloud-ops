"""Query Prometheus from OFF-cluster (the controller) via the kube-apiserver proxy.

Prometheus' ingress is SSO-gated (302), so we don't hit it directly. Instead we go through
the apiserver proxy with the controller's kubeconfig — no token, no SSO, cron-friendly:

    kubectl get --raw "/api/v1/namespaces/<ns>/services/<svc>:<port>/proxy/api/v1/query_range?..."

Only depends on `kubectl` being on PATH with a valid KUBECONFIG (the systemd unit sets it).
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.parse


class PrometheusError(RuntimeError):
    pass


def _raw(path: str) -> dict:
    proc = subprocess.run(
        ["kubectl", "get", "--raw", path],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise PrometheusError(proc.stderr.strip() or "kubectl get --raw failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise PrometheusError(f"non-JSON response: {exc}") from exc


_STEP_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _to_seconds(dur: str) -> int:
    return int(dur[:-1]) * _STEP_SECONDS[dur[-1]]


class Prometheus:
    def __init__(self, namespace: str, service: str, port: int = 9090):
        self.base = (f"/api/v1/namespaces/{namespace}/services/"
                     f"{service}:{port}/proxy/api/v1")

    def query_range(self, expr: str, window: str, step: str) -> list[float]:
        """Return the scalar series (float values) of `expr` over the last `window`.

        Assumes a single-series result (the queries in bands.json aggregate to one series).
        Empty results (e.g. a count with no matches) yield an empty list -> the caller treats
        that as an insufficient/absent signal, not a crash.
        """
        end = int(time.time())
        start = end - _to_seconds(window)
        params = urllib.parse.urlencode({
            "query": expr, "start": start, "end": end, "step": _to_seconds(step),
        })
        data = _raw(f"{self.base}/query_range?{params}")
        result = data.get("data", {}).get("result", [])
        if not result:
            return []
        return [float(v[1]) for v in result[0].get("values", [])]
