"""Unit tests for bands.json — the control-band config (Play 13). No cluster/network."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "sdlc_loop", "bands.json"), encoding="utf-8") as _fh:
    BANDS = json.load(_fh)


def _band(name):
    return next((b for b in BANDS["bands"] if b["name"] == name), None)


def test_bands_json_shape():
    assert BANDS["bands"], "no bands defined"
    for b in BANDS["bands"]:
        for k in ("name", "query", "direction"):
            assert b.get(k), f"band {b.get('name')!r} missing {k}"
        assert b["direction"] in ("high", "low", "both"), b["direction"]


def test_rollout_failures_matches_all_failure_phases():
    """Regression guard for the 2026-09-30 bug (minicloud-ops#6).

    Argo Rollouts' `rollout_info` metric reports a ProgressDeadlineExceeded failure as
    phase="Timeout" (a healthy rollout shows "Completed"), NOT "Degraded". The band query
    once matched only Degraded|Error, so it silently MISSED the most common rollout failure.
    The band MUST match every real failure phase, especially Timeout.
    """
    band = _band("rollout_failures")
    assert band is not None, "rollout_failures band missing"
    q = band["query"]
    for phase in ("Degraded", "Error", "Timeout", "Aborted"):
        assert phase in q, f"rollout_failures must match phase={phase!r} — query is: {q}"
    assert band["direction"] == "high"
    # `or vector(0)` keeps a continuous 0 baseline so a 0->1 jump trips the flat-baseline rule
    assert "or vector(0)" in q, "rollout_failures must fall back to 0 when no failures"


def test_delivery_and_reliability_bands_present():
    for name in ("pod_restarts_1h", "ingress_5xx_rate", "nodes_ready",
                 "open_p1_items", "rollout_failures"):
        assert _band(name) is not None, f"expected band {name!r}"


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
