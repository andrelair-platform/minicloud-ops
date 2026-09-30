"""Deterministic unit tests for the control-chart evaluator (no I/O, no cluster)."""
import math

from sdlc_loop.control_chart import evaluate


def _baseline(mean, sd, n=48):
    # a symmetric baseline with a known mean and (population) spread
    half = n // 2
    return [mean - sd] * half + [mean + sd] * (n - half)


def test_in_band():
    r = evaluate(_baseline(10, 1), current=10, direction="high")
    assert r.tier == 0 and r.action == "none"


def test_one_sigma():
    r = evaluate(_baseline(10, 1), current=11.0, direction="high")
    assert r.tier == 1 and r.action == "log"


def test_two_sigma():
    r = evaluate(_baseline(10, 1), current=12.0, direction="high")
    assert r.tier == 2 and r.action == "diagnose"


def test_three_sigma():
    r = evaluate(_baseline(10, 1), current=13.0, direction="high")
    assert r.tier == 3 and r.action == "propose"


def test_direction_high_ignores_drop():
    # a big drop is "good" for a high-direction metric -> not an alert
    r = evaluate(_baseline(10, 1), current=6.0, direction="high")
    assert r.tier == 0


def test_direction_low_alerts_on_drop():
    # nodes-Ready style: a drop is bad
    r = evaluate(_baseline(6, 1), current=3.0, direction="low")
    assert r.tier == 3


def test_direction_both():
    assert evaluate(_baseline(10, 1), current=7.0, direction="both").tier == 3
    assert evaluate(_baseline(10, 1), current=13.0, direction="both").tier == 3


def test_flat_baseline_jump_is_significant():
    r = evaluate([0.0] * 48, current=5.0, direction="high")
    assert r.tier == 3 and math.isinf(r.z)


def test_flat_baseline_no_change():
    r = evaluate([0.0] * 48, current=0.0, direction="high")
    assert r.tier == 0


def test_insufficient_baseline():
    r = evaluate([1.0, 2.0, 3.0], current=99.0, direction="high", min_samples=12)
    assert r.tier == 0 and "insufficient" in r.reason


if __name__ == "__main__":
    # tiny runner so it works without pytest on the controller
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
