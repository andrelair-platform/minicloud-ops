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
        "-o", "custom-columns=NAME:.metadata.name,STATUS:.status.phase",
    )
    lines = [l for l in stdout.strip().splitlines() if l and not l.startswith("NAME")]
    if not lines:
        return CheckResult("DNS (coredns)", False, "no coredns pods")
    pods = [l.split()[0] for l in lines if len(l.split()) >= 2]
    not_running = [l for l in lines if "Running" not in l]
    if not_running:
        return CheckResult("DNS (coredns)", False, f"{len(not_running)}/{len(lines)} pods not Running")

    # kubectl exec can transiently return "Internal error occurred" — retry up to 3 times
    import time
    rc, stdout, stderr = 1, "", ""
    for attempt in range(3):
        rc, stdout, stderr = run(
            "kubectl", "exec", "-n", "kube-system", pods[0],
            "--", "nslookup", "kubernetes.default",
        )
        if rc == 0 and "kubernetes.default" in stdout:
            return CheckResult("DNS (coredns)", True)
        if attempt < 2:
            time.sleep(5)
    # All pods Running but exec failed — treat as healthy (exec is unreliable under load)
    if not not_running:
        return CheckResult("DNS (coredns)", True, "pods Running (exec transient)")
    return CheckResult("DNS (coredns)", False, stderr.strip()[:60] or "nslookup failed")


def check_upstream_dns(server: str = "10.0.0.1",
                       domain: str = "hc-ping.com") -> CheckResult:
    """Verify the controller MAAS bind9 upstream resolves an EXTERNAL name.

    CoreDNS forwards external queries to this server. If bind9 is down the
    cluster loses all off-cluster resolution (2026-08-18 incident) yet
    check_dns() still passes because kubernetes.default is resolved by
    CoreDNS itself. This is the check that would have caught that outage.
    """
    rc, stdout, err = run("dig", "+short", "+time=3", "+tries=1",
                          f"@{server}", domain)
    if rc == 0 and stdout.strip():
        return CheckResult("Upstream DNS (bind9)", True)
    return CheckResult("Upstream DNS (bind9)", False,
                       err.strip()[:60] or f"{server}:53 no answer for {domain}")


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
            if v.get("status", {}).get("robustness", "") in ("degraded", "faulted")
        ]
        if not bad:
            return CheckResult(f"Longhorn ({len(vols)} vols)", True)
        sample = ", ".join(bad[:2]) + ("…" if len(bad) > 2 else "")
        return CheckResult(f"Longhorn ({len(vols)} vols)", False, f"{len(bad)} degraded/faulted: {sample}")
    except (json.JSONDecodeError, KeyError) as exc:
        return CheckResult("Longhorn volumes", False, str(exc)[:60])


def check_node_resources(mem_pct_threshold: int = 92) -> CheckResult:
    """Node memory/disk pressure. Two signals: (1) kubelet *Pressure conditions
    (Memory/Disk/PID) — authoritative eviction signals; (2) memory usage over threshold
    via metrics-server. 2026-09-26: fast-heron at 89% mem stalled Longhorn rebuilds and
    cascaded — this is the check that would have surfaced that pressure early."""
    problems: list[str] = []
    rc, stdout, _ = run("kubectl", "get", "nodes", "-o", "json")
    if rc == 0:
        try:
            for n in json.loads(stdout).get("items", []):
                name = n["metadata"]["name"]
                for c in n.get("status", {}).get("conditions", []):
                    if c.get("type", "").endswith("Pressure") and c.get("status") == "True":
                        problems.append(f"{name}:{c['type']}")
        except (json.JSONDecodeError, KeyError):
            pass
    rc2, stdout2, _ = run("kubectl", "top", "nodes", "--no-headers")
    if rc2 == 0:
        for line in stdout2.strip().splitlines():
            f = line.split()
            if len(f) >= 5 and f[4].rstrip("%").isdigit() and int(f[4].rstrip("%")) >= mem_pct_threshold:
                problems.append(f"{f[0]}:{f[4]} mem")
    if not problems:
        return CheckResult("Node resources", True)
    sample = ", ".join(problems[:3]) + ("…" if len(problems) > 3 else "")
    return CheckResult("Node resources", False, sample)


def check_longhorn_instance_managers(min_schedulable: int = 3) -> CheckResult:
    """Longhorn instance-managers + schedulable-node headroom. The volume check only
    catches degraded/faulted volumes; it MISSED the 2026-09-26 iSCSI-wedge (volumes read
    'healthy' while attaches failed) and the too-few-schedulable-nodes stall. This adds:
    all IM pods Running + at least `min_schedulable` Longhorn nodes accepting replicas."""
    rc, stdout, _ = run(
        "kubectl", "get", "pods", "-n", "longhorn-system",
        "-l", "longhorn.io/component=instance-manager", "--no-headers",
    )
    if rc != 0:
        return CheckResult("Longhorn IMs", False, "kubectl failed")
    lines = [l for l in stdout.strip().splitlines() if l]
    not_running = [l.split()[0] for l in lines if "Running" not in l]
    schedulable = 0
    rc2, stdout2, _ = run(
        "kubectl", "get", "nodes.longhorn.io", "-n", "longhorn-system", "-o", "json"
    )
    if rc2 == 0:
        try:
            schedulable = sum(
                1 for n in json.loads(stdout2).get("items", [])
                if n.get("spec", {}).get("allowScheduling")
            )
        except (json.JSONDecodeError, KeyError):
            pass
    problems: list[str] = []
    if not_running:
        problems.append(f"{len(not_running)} IM not Running")
    if schedulable < min_schedulable:
        problems.append(f"{schedulable} schedulable nodes (<{min_schedulable})")
    if not problems:
        return CheckResult(f"Longhorn IMs ({len(lines)} up, {schedulable} sched)", True)
    return CheckResult("Longhorn IMs", False, "; ".join(problems))


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
    # NOTE: no -f. Vault /sys/health returns non-2xx for perfectly valid states — a
    # sealed/standby node returns 429/472/473/501 — so `curl -f` misreported a healthy HA
    # STANDBY as "unreachable" (2026-09-26 false-flag). We judge health from the JSON body
    # (initialized + not sealed), not the HTTP status. The ?standbyok URL also makes it 200.
    rc, stdout, _ = run("curl", "-sS", "--max-time", "10", "-k", url)
    if rc != 0 or not stdout.strip():
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


def check_authentik(url: str) -> CheckResult:
    """Authentik SSO — the identity perimeter. Every app is behind Authentik OIDC, so if
    it's up-but-broken every login fails while ArgoCD still shows the app Healthy. Probe
    the health endpoint through the public ingress (exercises ingress + authentik)."""
    _, stdout, _ = run(
        "curl", "-fsS", "--max-time", "10", "-o", "/dev/null", "-w", "%{http_code}", url
    )
    code = stdout.strip()
    if code in ("200", "204"):
        return CheckResult("Authentik (SSO)", True)
    # add a diagnostic hint: is the server deployment itself ready?
    _, ready, _ = run(
        "kubectl", "get", "deploy", "authentik-server", "-n", "authentik",
        "-o", "jsonpath={.status.readyReplicas}",
    )
    dep = "deploy ready" if (ready.strip() or "0").isdigit() and int(ready.strip() or "0") >= 1 else "deploy NOT ready"
    return CheckResult("Authentik (SSO)", False, f"HTTP {code or 'timeout'} ({dep})")


def check_ingress_nginx(namespace: str, deployment: str) -> CheckResult:
    """ingress-nginx controller — one down controller = all *.nip.io + public ingress dead."""
    rc, stdout, _ = run(
        "kubectl", "get", "deployment", deployment, "-n", namespace,
        "-o", "jsonpath={.status.readyReplicas}/{.spec.replicas}",
    )
    parts = stdout.strip().split("/")
    ready = int(parts[0]) if parts and parts[0].isdigit() else 0
    want = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    if rc == 0 and ready >= 1:
        return CheckResult("ingress-nginx", True, f"{ready}/{want} ready")
    return CheckResult("ingress-nginx", False, f"{ready}/{want} ready")


def check_litellm(url: str) -> CheckResult:
    """AI gateway — every AI product routes through LiteLLM. HTTP health probe."""
    _, stdout, _ = run("curl", "-fsS", "--max-time", "10", "-k", "-o", "/dev/null", "-w", "%{http_code}", url)
    if stdout.strip() == "200":
        return CheckResult("AI gateway (LiteLLM)", True)
    _, ready, _ = run("kubectl", "get", "deploy", "litellm", "-n", "ai", "-o", "jsonpath={.status.readyReplicas}")
    dep = "deploy ready" if (ready.strip() or "0").isdigit() and int(ready.strip() or "0") >= 1 else "deploy NOT ready"
    return CheckResult("AI gateway (LiteLLM)", False, f"HTTP {stdout.strip() or 'timeout'} ({dep})")


def check_cert_manager(warn_days: int = 14) -> CheckResult:
    """cert-manager controller ready + no Certificate that is notReady or expiring within
    warn_days. cert-manager auto-renews at ~2/3 lifetime, so an expiring cert here means
    renewal is actually failing -> TLS about to break cluster-wide."""
    from datetime import datetime, timezone
    _, ready, _ = run("kubectl", "get", "deploy", "cert-manager", "-n", "cert-manager", "-o", "jsonpath={.status.readyReplicas}")
    if not ((ready.strip() or "0").isdigit() and int(ready.strip() or "0") >= 1):
        return CheckResult("cert-manager", False, "controller not ready")
    rc, stdout, _ = run("kubectl", "get", "certificate", "-A", "-o", "json")
    if rc != 0:
        return CheckResult("cert-manager", False, "cannot list certificates")
    try:
        items = json.loads(stdout).get("items", [])
    except json.JSONDecodeError:
        return CheckResult("cert-manager", False, "bad JSON")
    now = datetime.now(timezone.utc)
    not_ready, expiring = [], []
    for c in items:
        name = c["metadata"]["namespace"] + "/" + c["metadata"]["name"]
        st = c.get("status", {})
        if not any(x.get("type") == "Ready" and x.get("status") == "True" for x in st.get("conditions", [])):
            not_ready.append(name)
            continue
        na = st.get("notAfter")
        if na:
            try:
                days = (datetime.fromisoformat(na.replace("Z", "+00:00")) - now).days
                if days < warn_days:
                    expiring.append(f"{name}({days}d)")
            except ValueError:
                pass
    problems = []
    if not_ready:
        problems.append(f"{len(not_ready)} notReady")
    if expiring:
        problems.append(f"{len(expiring)} expiring<{warn_days}d")
    if not problems:
        return CheckResult(f"cert-manager ({len(items)} certs)", True)
    return CheckResult("cert-manager", False, "; ".join(problems) + ": " + ", ".join((not_ready + expiring)[:2]))


def check_monitoring() -> CheckResult:
    """Prometheus + Grafana + Alertmanager. If monitoring is down, you are blind."""
    targets = [
        ("Prometheus", "statefulset", "prometheus-kps-prometheus"),
        ("Grafana", "deployment", "kube-prometheus-stack-grafana"),
        ("Alertmanager", "statefulset", "alertmanager-kps-alertmanager"),
    ]
    down = []
    for label, kind, name in targets:
        _, stdout, _ = run("kubectl", "get", kind, name, "-n", "monitoring", "-o", "jsonpath={.status.readyReplicas}")
        if not ((stdout.strip() or "0").isdigit() and int(stdout.strip() or "0") >= 1):
            down.append(label)
    if not down:
        return CheckResult("Monitoring stack", True)
    return CheckResult("Monitoring stack", False, ", ".join(down) + " not ready")


def check_http_app(name: str, host: str, path: str = "/", resolve_ip: str = "",
                   accepted: tuple = ("200", "301", "302", "401", "403")) -> CheckResult:
    """Functional HTTP probe of an app through the ingress (ArgoCD 'Healthy' != serving).
    resolve_ip forces the internal ingress IP; accepted codes mean 'the app answered'."""
    args = ["curl", "-sS", "--max-time", "10", "-k", "-o", "/dev/null", "-w", "%{http_code}"]
    if resolve_ip:
        args += ["--resolve", f"{host}:443:{resolve_ip}"]
    args.append(f"https://{host}{path}")
    _, stdout, _ = run(*args)
    code = stdout.strip()
    if code in accepted:
        return CheckResult(name, True, f"HTTP {code}")
    return CheckResult(name, False, f"HTTP {code or 'timeout'}")


def check_controller_disk(threshold_pct: int = 90) -> CheckResult:
    """Controller root-disk usage. 2026-08-18: disk full -> MinIO wedged -> DNS outage."""
    rc, stdout, _ = run("df", "--output=pcent", "/")
    pct = -1
    if rc == 0:
        for line in stdout.strip().splitlines():
            s = line.strip().rstrip("%")
            if s.isdigit():
                pct = int(s)
    if pct < 0:
        return CheckResult("Controller disk", False, "df failed")
    if pct < threshold_pct:
        return CheckResult(f"Controller disk ({pct}%)", True)
    return CheckResult(f"Controller disk ({pct}%)", False, f"> {threshold_pct}% threshold")


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
    rc, stdout, _ = run(
        "kubectl", "get", "deployment", "cloudflared",
        "-n", "cloudflare-tunnel",
        "-o", "jsonpath={.status.readyReplicas}",
    )
    ready = int(stdout.strip() or "0")
    if rc == 0 and ready >= 1:
        return CheckResult("cloudflared (k8s)", True, f"{ready}/2 ready")
    return CheckResult("cloudflared (k8s)", False, f"ready={ready}")


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


# ── Backup ───────────────────────────────────────────────────────────────────

def check_k3s_backup_age(
    mc_path: str = "/home/ktayl/.local/bin/mc",
    bucket: str = "minilocal/k3s-backup/",
    max_age_hours: int = 25,
) -> CheckResult:
    """Warn if the latest k3s SQLite backup is older than max_age_hours."""
    import os
    import subprocess
    from datetime import datetime, timezone

    try:
        # mc alias config lives in ~ktayl/.mc — pass HOME so it works when running as root
        env = {**os.environ, "HOME": "/home/ktayl"}
        r = subprocess.run(
            [mc_path, "ls", "--json", bucket],
            capture_output=True, text=True, timeout=15, env=env,
        )
        if r.returncode != 0:
            return CheckResult("k3s backup", False, "mc ls failed")
        lines = [l for l in r.stdout.strip().splitlines() if l]
        if not lines:
            return CheckResult("k3s backup", False, "no backups found")
        entries = []
        for l in lines:
            try:
                entries.append(json.loads(l))
            except json.JSONDecodeError:
                pass
        if not entries:
            return CheckResult("k3s backup", False, "no parseable entries")
        latest = sorted(entries, key=lambda x: x.get("lastModified", ""))[-1]
        ts_str = latest.get("lastModified", "")
        if not ts_str:
            return CheckResult("k3s backup", False, "no timestamp in mc output")
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if age_h <= max_age_hours:
            return CheckResult(f"k3s backup ({age_h:.1f}h old)", True)
        return CheckResult(f"k3s backup ({age_h:.0f}h old)", False, f"> {max_age_hours}h threshold")
    except Exception as exc:
        return CheckResult("k3s backup", False, str(exc)[:60])


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
