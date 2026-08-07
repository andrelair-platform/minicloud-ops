"""
All platform health checks.

Each function returns a CheckResult. Add new checks here and register them
in main.py — no other file needs to change.
"""
import json

from .models import CheckResult
from .runner import run


# ── Network ───────────────────────────────────────────────────────────────────

def check_internet(url: str = "https://1.1.1.1") -> CheckResult:
    rc, _, err = run("curl", "-fsS", "--max-time", "10", url)
    if rc == 0:
        return CheckResult("Internet/NAT", True)
    return CheckResult("Internet/NAT", False, err.strip()[:60] or "no route")


def check_dns() -> CheckResult:
    rc, stdout, _ = run(
        "kubectl", "get", "pods", "-n", "kube-system",
        "-l", "k8s-app=kube-dns", "--no-headers",
        "-o", "custom-columns=NAME:.metadata.name",
    )
    pods = [p for p in stdout.strip().splitlines() if p and p != "NAME"]
    if not pods:
        return CheckResult("DNS (coredns)", False, "no coredns pods")
    rc, stdout, stderr = run(
        "kubectl", "exec", "-n", "kube-system", pods[0],
        "--", "nslookup", "kubernetes.default",
    )
    if rc == 0 and "kubernetes.default" in stdout:
        return CheckResult("DNS (coredns)", True)
    return CheckResult("DNS (coredns)", False, stderr.strip()[:60] or "nslookup failed")


# ── Kubernetes ────────────────────────────────────────────────────────────────

def check_k3s_nodes(expected: int = 5) -> CheckResult:
    rc, stdout, _ = run("kubectl", "get", "nodes", "--no-headers")
    if rc != 0:
        return CheckResult(f"k3s nodes (/{expected})", False, "kubectl unreachable")
    lines = [l for l in stdout.strip().splitlines() if l]
    total = len(lines)
    not_ready = sum(1 for l in lines if "NotReady" in l)
    if not_ready == 0 and total >= expected:
        return CheckResult(f"k3s nodes ({total}/{expected})", True)
    return CheckResult(f"k3s nodes ({total}/{expected})", False, f"NotReady={not_ready}")


def check_longhorn_volumes() -> CheckResult:
    rc, stdout, _ = run(
        "kubectl", "get", "volumes.longhorn.io", "-n", "longhorn-system", "-o", "json"
    )
    if rc != 0:
        return CheckResult("Longhorn volumes", False, "kubectl failed")
    try:
        vols = json.loads(stdout).get("items", [])
        bad = [
            v["metadata"]["name"] for v in vols
            if v.get("status", {}).get("robustness", "") not in ("healthy", "")
        ]
        if not bad:
            return CheckResult(f"Longhorn ({len(vols)} vols)", True)
        sample = ", ".join(bad[:2]) + ("…" if len(bad) > 2 else "")
        return CheckResult(f"Longhorn ({len(vols)} vols)", False, f"{len(bad)} degraded: {sample}")
    except (json.JSONDecodeError, KeyError) as exc:
        return CheckResult("Longhorn volumes", False, str(exc)[:60])


def check_pvcs() -> CheckResult:
    rc, stdout, _ = run("kubectl", "get", "pvc", "-A", "--no-headers")
    if rc != 0:
        return CheckResult("PVCs", False, "kubectl failed")
    lines = [l for l in stdout.strip().splitlines() if l]
    unbound = [l for l in lines if "Bound" not in l]
    if not unbound:
        return CheckResult(f"PVCs ({len(lines)} bound)", True)
    return CheckResult(f"PVCs ({len(lines)} total)", False, f"{len(unbound)} not Bound")


def check_argocd_apps() -> CheckResult:
    rc, stdout, _ = run(
        "kubectl", "get", "application", "-n", "argocd", "-o", "json"
    )
    if rc != 0:
        return CheckResult("ArgoCD apps", False, "kubectl failed")
    try:
        items = json.loads(stdout).get("items", [])
        bad = [
            a["metadata"]["name"] for a in items
            if a.get("status", {}).get("health", {}).get("status", "") in ("Degraded", "Missing")
        ]
        total = len(items)
        if not bad:
            return CheckResult(f"ArgoCD ({total} apps)", True)
        sample = ", ".join(bad[:2]) + ("…" if len(bad) > 2 else "")
        return CheckResult(f"ArgoCD ({total} apps)", False, f"{len(bad)} Degraded: {sample}")
    except (json.JSONDecodeError, KeyError) as exc:
        return CheckResult("ArgoCD apps", False, str(exc)[:60])


def check_postgres(namespace: str, pod: str) -> CheckResult:
    # -h 127.0.0.1 forces TCP; -U postgres required (PG 18 returns exit 3 without explicit user).
    # bash -c wrapper ensures the exit code is properly propagated through kubectl exec.
    rc, _, stderr = run(
        "kubectl", "exec", "-n", namespace, pod, "--",
        "bash", "-c", "pg_isready -h 127.0.0.1 -U postgres -q",
    )
    label = f"PostgreSQL ({namespace})"
    if rc == 0:
        return CheckResult(label, True)
    return CheckResult(label, False, stderr.strip()[:60] or f"pg_isready exit={rc}")


# ── Services ──────────────────────────────────────────────────────────────────

def check_vault(url: str) -> CheckResult:
    rc, stdout, _ = run("curl", "-fsS", "--max-time", "10", "-k", url)
    if rc != 0:
        return CheckResult("Vault", False, "unreachable")
    try:
        data = json.loads(stdout)
        if not data.get("initialized"):
            return CheckResult("Vault", False, "not initialized")
        if data.get("sealed"):
            return CheckResult("Vault", False, "sealed")
        return CheckResult("Vault", True)
    except json.JSONDecodeError:
        return CheckResult("Vault", False, "bad JSON response")


def check_harbor() -> CheckResult:
    _, stdout, _ = run(
        "kubectl", "get", "deployment", "-n", "harbor", "harbor-core",
        "-o", "jsonpath={.status.readyReplicas}",
    )
    ready = int(stdout.strip()) if stdout.strip().isdigit() else 0
    if ready >= 1:
        return CheckResult("Harbor", True)
    return CheckResult("Harbor", False, "harbor-core not ready")


def check_minio_docker() -> CheckResult:
    _, stdout, _ = run("docker", "inspect", "minio", "--format", "{{.State.Status}}")
    state = stdout.strip()
    if state == "running":
        return CheckResult("MinIO (docker)", True)
    return CheckResult("MinIO (docker)", False, state or "container not found")


def check_cloudflared() -> CheckResult:
    rc, _, _ = run("systemctl", "is-active", "cloudflared")  # noqa: F841
    if rc == 0:
        return CheckResult("cloudflared", True)
    return CheckResult("cloudflared", False, "inactive")


def check_tailscale() -> CheckResult:
    rc, stdout, _ = run("tailscale", "status", "--json", timeout=10)
    if rc != 0:
        return CheckResult("Tailscale", False, "tailscale status failed")
    try:
        data = json.loads(stdout)
        state = data.get("BackendState", "Unknown")
        if state != "Running":
            return CheckResult("Tailscale", False, f"state={state}")
        peers = data.get("Peer", {})
        return CheckResult(f"Tailscale ({len(peers)} peers)", True)
    except json.JSONDecodeError:
        # Fallback to text output
        rc2, stdout2, _ = run("tailscale", "status")
        if rc2 == 0 and stdout2.strip():
            return CheckResult("Tailscale", True)
        return CheckResult("Tailscale", False, "no peer list")


# ── Public ────────────────────────────────────────────────────────────────────

def check_public_endpoint(url: str) -> CheckResult:
    _, stdout, _ = run(
        "curl", "-fsS", "--max-time", "10",
        "-o", "/dev/null", "-w", "%{http_code}", url,
    )
    code = stdout.strip()
    hostname = url.split("//")[-1].split("/")[0]
    if code in ("200", "301", "302"):
        return CheckResult(f"Public ({hostname})", True)
    return CheckResult(f"Public ({hostname})", False, f"HTTP {code or 'timeout'}")
