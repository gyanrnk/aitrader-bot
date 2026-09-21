"""Lock the Delta carry verdict logic against regressions.

The one bug this guards hardest: net-of-cost and "above the 50%/yr bar" are DIFFERENT
conditions. A steady low funding that never nears the bar can still clear cost over weeks
(THIN), and that must not be mislabelled as a rich opportunity — nor a real fat spike as
thin. Each case pins the verdict to the RIGHT regime.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitrader.research import delta_carry as dc

END = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def _rows(days: float, fr: float, symbol: str = "XRPUSD", end: datetime = END,
          step_h: int = 1) -> list[dict]:
    """Hourly synthetic rows for `days` at a constant 8h funding `fr` (in percent)."""
    out, t = [], end - timedelta(days=days)
    while t <= end:
        out.append({"ts": t.isoformat(), "symbol": symbol,
                    "funding_pct_8h": fr, "annual_funding_pct": fr * 3 * 365,
                    "mark_price": 2.5, "hedgeable": True, "go": fr * 3 * 365 >= 50})
        t += timedelta(hours=step_h)
    return out


def test_rich_sustained_is_candidate():
    # 0.06%/8h ≈ 66%/yr held 10 days: short hold clears cost at a rich APR.
    res = dc.analyze(_rows(10, 0.060), "XRPUSD")
    assert res["ok"] and res["verdict"]["code"] == "CANDIDATE", res["verdict"]
    assert res["verdict"]["go_now"] is True                      # 66% ≥ 50 bar


def test_thin_steady_is_thin_not_candidate():
    # 0.011%/8h ≈ 12%/yr held 30 days: clears cost ONLY over weeks — real but marginal.
    res = dc.analyze(_rows(30, 0.011), "XRPUSD")
    assert res["verdict"]["code"] == "THIN", res["verdict"]
    assert res["verdict"]["go_now"] is False                     # never nears the bar
    w30 = next(w for w in res["windows"] if w["days"] == 30)
    assert w30["net"] > 0 and w30["above"] == 0                  # net+ yet 0 above bar


def test_short_thin_history_is_below():
    # 5 days at baseline: no hold horizon in-range clears the 0.40% round trip.
    res = dc.analyze(_rows(5, 0.011), "XRPUSD")
    assert res["verdict"]["code"] == "BELOW", res["verdict"]
    assert all(w["net"] < 0 for w in res["windows"])


def test_negative_funding_is_flip():
    res = dc.analyze(_rows(10, -0.030), "XRPUSD")
    assert res["verdict"]["code"] == "FLIP", res["verdict"]


def test_settlements_collapse_to_one_per_8h_bucket():
    # 3 days of HOURLY samples -> exactly one representative point per 8h settlement.
    setts = dc.settlements(_rows(3, 0.02, step_h=1), "XRPUSD")
    # 3 days => 9 completed 8h buckets (boundary inclusive can add one); allow 9–10.
    assert 9 <= len(setts) <= 10, len(setts)
    assert all(s["funding_8h"] == 0.02 for s in setts)


def test_hottest_picks_richest_latest():
    rows = _rows(10, 0.011, symbol="BTCUSD") + _rows(10, 0.055, symbol="XRPUSD")
    assert dc.hottest(rows) == "XRPUSD"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print(f"\nall {len(fns)} delta_carry tests passed")
