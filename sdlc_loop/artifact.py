"""Turn a control-band breach into the loop's re-entry artifact (Play 13).

Tier 2 (diagnose) writes an `intent.md` in the AI-native Play-1 shape; Tier 3 (propose) also
opens a GitHub issue so it surfaces on the board. The intent.md needs NO credential — the
GitHub issue is the only part that needs a scoped token, so the core loop works token-less.

The human then runs Claude Code locally against the intent.md to diagnose/fix — the model
step stays on the owner's plan, never metered/headless here.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone

from .control_chart import BandResult


def _intent_markdown(band: dict, r: BandResult, samples: list[float]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    recent = ", ".join(f"{v:g}" for v in samples[-8:])
    return f"""# Intent: investigate {band['name']} control-band breach

Author: sdlc-loop (automated detector). Status: draft. Generated: {now}.

## Problem
The metric **{band['name']}** ({band.get('description', '')}) breached its control band at
the **{r.action}** tier. This is a deterministic control-chart detection (no model involved).

- query: `{band['query']}`
- current: **{r.current:g}**  ·  baseline mean: {r.mean:g}  ·  sd: {r.std:g}  ·  n={r.n}
- z-score: **{r.z:+.2f}** (direction={band.get('direction', 'high')})
- recent samples: {recent}
- verdict: {r.reason}

## Proposed outcome
Diagnose the cause and either remediate or record it as expected. If it's a real regression,
the fix flows through the normal chain (plan.md -> PR -> review -> Kargo). If it's noise,
tune the band in `sdlc_loop/bands.json`.

## Affected users and systems
Whatever owns `{band['name']}` — inspect the contributing pods/services in Grafana/Prometheus.

## Constraints
Diagnosis runs via Claude Code on the owner's plan (not metered). Any prod change goes
through CODEOWNERS + Kargo; the detector itself only observes and files this artifact.

## Open questions
- Real regression, or baseline drift that should re-tune the band?
- Does this correlate with a recent deploy (check the change-record issues)?

## How to act
Run Claude Code locally against this file, e.g.:
`claude "read this intent.md, diagnose {band['name']}, propose the smallest safe fix"`
"""


def write_intent(intent_dir: str, band: dict, r: BandResult, samples: list[float]) -> str:
    os.makedirs(intent_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(intent_dir, f"{stamp}-{band['name']}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_intent_markdown(band, r, samples))
    return path


def open_github_issue(repo: str, token: str, band: dict, r: BandResult,
                      samples: list[float]) -> int | None:
    """Open a GitHub issue with the intent as its body. Returns the issue number, or None
    on failure (a detector must never crash the timer)."""
    body = {
        "title": f"[LOOP] {band['name']} breached {r.action} band (z={r.z:+.2f})",
        "body": _intent_markdown(band, r, samples),
        "labels": ["sdlc-loop", "enhancement"],
    }
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "minicloud-sdlc-loop",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("number")
    except Exception:
        return None
