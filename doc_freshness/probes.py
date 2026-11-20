"""Live-cluster probes for the docs-freshness checker.

Each probe is a small, named function that reads a single fact from the LIVE cluster via `kubectl`
(KUBECONFIG is set by the entry-point wrapper). Probes return a plain int or a sorted list of strings
so the checker can compare them against the value a doc asserts. Keeping the probes in code (rather than
embedding shell in the claims file) means there is no command-injection surface and each probe is unit-
testable. Add a probe here, then reference it by name from `claims.json`.
"""

from __future__ import annotations

import subprocess


def _kubectl(args: list[str], timeout: int = 30) -> str:
    """Run `kubectl <args>` and return stdout (empty string on any failure — a probe never raises)."""
    try:
        r = subprocess.run(
            ["kubectl", *args], capture_output=True, text=True, timeout=timeout, check=False
        )
        return r.stdout if r.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def _count_lines(text: str) -> int:
    return len([ln for ln in text.splitlines() if ln.strip()])


def count_resource(kind: str, namespace: str | None = None, selector: str | None = None) -> int:
    """Count objects of `kind`. namespace="all" → `-A`; a name → `-n <ns>`; None → current ns."""
    args = ["get", kind]
    if namespace == "all":
        args.append("-A")
    elif namespace:
        args += ["-n", namespace]
    if selector:
        args += ["-l", selector]
    args.append("--no-headers")
    return _count_lines(_kubectl(args))


def k3s_versions() -> list[str]:
    """The distinct kubelet versions across all nodes (sorted) — a single-element list when uniform."""
    out = _kubectl(["get", "nodes", "-o", "jsonpath={.items[*].status.nodeInfo.kubeletVersion}"])
    return sorted({v for v in out.split() if v})


# Registry: the names claims.json may reference.
PROBES = {
    "count_resource": count_resource,
    "k3s_versions": k3s_versions,
}
