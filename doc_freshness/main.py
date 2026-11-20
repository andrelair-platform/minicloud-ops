"""Docs-freshness checker — "is this doc still true against the live cluster?"

Published docs assert concrete live facts (node count, k3s version, ArgoCD app count, PrometheusRule
count, Grafana dashboards, Gatekeeper constraints…). Those drift slowly and silently as the platform
grows, so a page that was accurate at merge rots. This deterministic check reads each asserted fact
from the LIVE cluster (`doc_freshness/probes.py`) and compares it to the value the doc declares
(`doc_freshness/claims.json`). On drift it writes a report the owner already watches
(`~/minicloud-ops-intents/docs-freshness.md`) and exits non-zero so the systemd timer surfaces it.

NO model is called and NO doc is edited — diagnosis + the one-line doc fix is a human (or a human running
Claude Code). This is the docs-side twin of `sdlc_loop`: a deterministic detector, a human remediator.

Usage:
    python3 -m doc_freshness.main              # run, write report, exit 1 on drift
    python3 -m doc_freshness.main --dry-run    # run + print, never writes a file
    python3 -m doc_freshness.main --json       # machine-readable result
"""

# pyright: reportMissingImports=false
# (runs on the controller with PYTHONPATH=/usr/local/lib/minicloud, where `doc_freshness` is symlinked —
#  same pattern as sdlc_loop; local Pyright can't resolve the sibling import.)
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from doc_freshness.probes import PROBES

_CLAIMS = Path(__file__).with_name("claims.json")
_REPORT_DIR = Path(os.path.expanduser("~/minicloud-ops-intents"))
_REPORT = _REPORT_DIR / "docs-freshness.md"


def _compare(live, expect, compare: str, tolerance: int) -> bool:
    if compare == "eq":
        return live == expect
    if compare == "gte":
        return isinstance(live, int) and live >= expect
    if compare == "lte":
        return isinstance(live, int) and live <= expect
    if compare == "approx":
        return isinstance(live, int) and abs(live - expect) <= tolerance
    if compare == "set_eq":
        return sorted(live) == sorted(expect)
    return False


def _evaluate() -> list[dict]:
    claims = json.loads(_CLAIMS.read_text())["claims"]
    results = []
    for c in claims:
        probe = PROBES.get(c["probe"])
        if probe is None:
            results.append({**c, "live": None, "ok": False, "error": f"unknown probe {c['probe']!r}"})
            continue
        live = probe(**c.get("args", {}))
        ok = _compare(live, c["expect"], c.get("compare", "eq"), c.get("tolerance", 0))
        results.append({**c, "live": live, "ok": ok})
    return results


def _render(results: list[dict], ts: str) -> str:
    drift = [r for r in results if not r["ok"]]
    lines = [
        "# Docs-freshness report",
        "",
        f"_Generated {ts} by `minicloud-docs-freshness` (deterministic; no model, no doc edited)._",
        "",
        f"**{len(results) - len(drift)}/{len(results)} claims fresh**"
        + ("" if not drift else f" — **{len(drift)} DRIFTED** ⚠️"),
        "",
        "| Claim | Doc | Expected | Live | |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        mark = "✅" if r["ok"] else "❌"
        live = r.get("error") or r["live"]
        lines.append(f"| {r['id']} — {r['desc']} | `{r['doc']}` | {r['expect']} | {live} | {mark} |")
    if drift:
        lines += [
            "",
            "## Action — a drifted claim means the doc no longer matches the cluster",
            "For each ❌: update the doc at the listed `doc` page / anchor to the live value (or fix the",
            "cluster if the doc states the intended state), then bump `expect` in",
            "`minicloud-ops/doc_freshness/claims.json` to match so the check passes again.",
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Check published docs against the live cluster.")
    ap.add_argument("--dry-run", action="store_true", help="print only; never write the report file")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    results = _evaluate()
    drift = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({"timestamp": ts, "drifted": len(drift), "results": results}, default=str))
    else:
        print(_render(results, ts))

    if not args.dry_run:
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        _REPORT.write_text(_render(results, ts))

    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
