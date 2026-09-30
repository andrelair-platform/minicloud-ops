"""minicloud SDLC closing-the-loop detector (Play 13) — entry point.

Deterministic: query each control band from Prometheus (via the apiserver proxy), evaluate
against its rolling baseline, and act by tier:

    tier 0  in-band   -> nothing
    tier 1  1sigma    -> log
    tier 2  2sigma    -> write an intent.md
    tier 3  3sigma    -> write an intent.md + open a GitHub issue (if a token is present)

NO model is called here — detection + escalation are 100% deterministic. The intent.md/issue
re-enters the AI-native loop; a human then runs Claude Code (on-plan) to diagnose.

Usage:
    minicloud-sdlc-loop            # installed entry point (one pass)
    python3 -m sdlc_loop.main --dry-run    # never opens issues
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from .artifact import open_github_issue, write_intent
from .control_chart import evaluate
from .prometheus import Prometheus, PrometheusError

HERE = os.path.dirname(os.path.abspath(__file__))


def _log(level: str, msg: str) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"{ts} [{level}] {msg}", flush=True)


def _load_config(path: str | None) -> dict:
    with open(path or os.path.join(HERE, "bands.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _github_token() -> str | None:
    tok = os.environ.get("SDLC_LOOP_GH_TOKEN")
    if tok:
        return tok.strip()
    f = os.path.expanduser("~/.sdlc-loop-github-token")
    if os.path.exists(f):
        with open(f, encoding="utf-8") as fh:
            return fh.read().strip() or None
    return None


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    cfg = _load_config(None)
    base = cfg["baseline"]
    sigmas = tuple(cfg.get("sigmas", [1.0, 2.0, 3.0]))
    intent_dir = os.path.expanduser(cfg.get("intent_dir", "~/minicloud-ops-intents"))
    gh = cfg.get("github", {})
    open_from = gh.get("open_issue_from_tier", 3)
    token = None if dry_run else _github_token()

    prom = Prometheus(**cfg["prometheus"])
    breaches = 0

    for band in cfg["bands"]:
        name = band["name"]
        try:
            values = prom.query_range(band["query"], base["window"], base["step"])
        except PrometheusError as exc:
            _log("ERROR", f"{name}: query failed: {exc}")
            continue

        if len(values) < base["min_samples"] + 1:
            _log("INFO", f"{name}: insufficient samples ({len(values)}) — skipped")
            continue

        baseline, current = values[:-1], values[-1]
        r = evaluate(baseline, current, band.get("direction", "high"),
                     sigmas, base["min_samples"])

        if r.tier == 0:
            _log("DEBUG", f"{name}: in-band ({r.reason})")
            continue

        breaches += 1
        _log("WARN", f"{name}: TIER {r.tier} ({r.action}) — {r.reason}")

        if r.tier >= 2:
            path = write_intent(intent_dir, band, r, values)
            _log("INFO", f"{name}: wrote intent {path}")

        if r.tier >= open_from:
            repo = gh.get("repo")
            if dry_run:
                _log("INFO", f"{name}: dry-run — would open issue on {repo}")
            elif not token:
                _log("INFO", f"{name}: no token (~/.sdlc-loop-github-token) — issue skipped")
            elif repo:
                num = open_github_issue(repo, token, band, r, values)
                _log("INFO", f"{name}: opened issue #{num} on {repo}" if num
                     else f"{name}: issue creation failed (see token/scope)")

    _log("INFO", f"done — {len(cfg['bands'])} bands checked, {breaches} breach(es)")
    return 0  # a detector must never fail its timer


if __name__ == "__main__":
    sys.exit(main())
