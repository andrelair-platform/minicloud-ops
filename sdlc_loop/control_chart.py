"""Deterministic control-chart evaluation (AI-native SDLC Play 13 — closing the loop).

Pure math, no I/O, fully unit-testable. Given a baseline window of samples and the current
value, classify how anomalous the current value is into a response TIER:

    0 = in-band (nothing)
    1 = 1sigma  -> log
    2 = 2sigma  -> diagnose (write an intent.md)
    3 = 3sigma  -> propose  (write an intent.md + open a GitHub issue)

`direction` filters which way is "bad": most reliability metrics (5xx, restarts, failures)
only matter when they go UP ("high"); a healthy-count metric (nodes Ready) matters when it
goes DOWN ("low"); "both" alerts either way. This keeps the detector 100% deterministic —
no model is involved in deciding whether to escalate.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass
class BandResult:
    tier: int          # 0..3
    z: float           # signed z-score of current vs baseline
    mean: float
    std: float
    current: float
    n: int             # baseline sample count
    reason: str

    @property
    def action(self) -> str:
        return {0: "none", 1: "log", 2: "diagnose", 3: "propose"}[self.tier]


def evaluate(
    baseline: list[float],
    current: float,
    direction: str = "high",
    sigmas: tuple[float, float, float] = (1.0, 2.0, 3.0),
    min_samples: int = 12,
) -> BandResult:
    """Classify `current` against the `baseline` distribution. Deterministic."""
    n = len(baseline)
    if n < min_samples:
        return BandResult(0, 0.0, float("nan"), float("nan"), current, n,
                          f"insufficient baseline ({n} < {min_samples})")

    mean = statistics.fmean(baseline)
    std = statistics.pstdev(baseline)  # population std over the window

    if std == 0:
        # A flat baseline: any deviation is, by definition, unprecedented.
        if current == mean:
            z = 0.0
        else:
            z = math.inf if current > mean else -math.inf
    else:
        z = (current - mean) / std

    # direction gate — ignore movement in the "good" direction
    if direction == "high" and z <= 0:
        return BandResult(0, z, mean, std, current, n, "within band (good direction)")
    if direction == "low" and z >= 0:
        return BandResult(0, z, mean, std, current, n, "within band (good direction)")

    az = abs(z)
    s1, s2, s3 = sigmas
    if az >= s3:
        tier = 3
    elif az >= s2:
        tier = 2
    elif az >= s1:
        tier = 1
    else:
        tier = 0

    zs = "inf" if math.isinf(z) else f"{z:+.2f}"
    reason = (f"current={current:g} vs mean={mean:g} sd={std:g} "
              f"z={zs} -> {['in-band','1sigma','2sigma','3sigma'][tier]}")
    return BandResult(tier, z, mean, std, current, n, reason)
