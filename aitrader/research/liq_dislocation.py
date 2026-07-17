"""Is there actually a discount in forced liquidations? — the decisive, model-free test.

Hypothesis `liq_meanrev`: "Forced liquidations overshoot price; I provide liquidity into
the cascade and fade it."

We do NOT need a backtest to falsify this. Every Kraken execution carries `markPrice` at
that instant, so the dislocation is directly observable:

    adverse_bps = signed((fill - mark) / mark) * 1e4      # sign folded by direction
    adverse_bps > 0  <=>  the forced order filled WORSE than mark
                     <=>  a discount was available to whoever took the other side (us)

If forced sells fill AT or ABOVE mark, there is no discount and the premise is dead —
no backtest required. This is the cheapest possible falsification.

WHY THIS IS NECESSARY BUT NOT SUFFICIENT: `adverse_bps` is the INSTANT edge, measured at
the moment of the fill, before any inventory risk. Providing liquidity means resting an
order, getting hit, and then HOLDING the position while mark moves against you. So:
  * median adverse_bps <= cost  => definitively dead (you can't even win at t=0)
  * median adverse_bps >  cost  => necessary condition met; the backtest then has to show
                                   the edge survives inventory risk, which it may not.

NOTIONAL WEIGHTING IS NOT OPTIONAL. Kraken's EPP shreds liquidations into 10% child
orders — observed fills range from ~$12 to large. An unweighted median counts a $12 fill
the same as a $50k one, which is not the economics you would actually trade. We report
both and treat the notional-weighted number as the decision-relevant one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _wmedian(values: np.ndarray, weights: np.ndarray) -> float:
    """Weighted median — the notional-weighted centre of the dislocation distribution."""
    if len(values) == 0 or weights.sum() <= 0:
        return float("nan")
    order = np.argsort(values)
    v, w = values[order], weights[order]
    c = np.cumsum(w) / w.sum()
    return float(v[np.searchsorted(c, 0.5)])


def analyze(liq: pd.DataFrame, cost_bps: float = 5.0) -> dict:
    """Per-symbol + pooled dislocation stats.

    cost_bps = round-trip cost of providing liquidity (Kraken maker ~2bps/side + spread).
    The pre-registered bar: notional-weighted median adverse_bps must EXCEED this.
    """
    out = {}
    for sym, g in list(liq.groupby("symbol")) + [("__POOLED__", liq)]:
        a = g["adverse_bps"].to_numpy(dtype=float)
        n = g["usd_value"].to_numpy(dtype=float)
        if len(a) == 0:
            continue
        wmed = _wmedian(a, n)
        out[sym] = {
            "n": int(len(a)),
            "usd_total": round(float(n.sum()), 0),
            "usd_median": round(float(np.median(n)), 2),
            "median_bps": round(float(np.median(a)), 2),
            "wmedian_bps": round(wmed, 2),              # <- decision-relevant
            "mean_bps": round(float(a.mean()), 2),
            "p25_bps": round(float(np.percentile(a, 25)), 2),
            "p75_bps": round(float(np.percentile(a, 75)), 2),
            "pct_adverse": round(float((a > 0).mean()), 3),   # share filling worse than mark
            "pct_beat_cost": round(float((a > cost_bps).mean()), 3),
            "verdict": _verdict(wmed, cost_bps),
        }
    return out


def _verdict(wmed: float, cost_bps: float) -> str:
    """The bar, pre-registered in research/hypotheses.json BEFORE the data was pulled."""
    if not np.isfinite(wmed):
        return "NO DATA"
    if wmed <= 0:
        return "PREMISE FALSE — forced fills are not at a discount. Reject, no backtest."
    if wmed <= cost_bps:
        return f"REAL BUT UNCAPTURABLE — discount {wmed:.2f}bps < cost {cost_bps}bps. Reject."
    return f"NECESSARY CONDITION MET — {wmed:.2f}bps > {cost_bps}bps. Proceed to gauntlet."


def by_direction(liq: pd.DataFrame) -> dict:
    """Sell = a LONG was force-closed (engine sells). Buy = a SHORT was force-closed.

    Asymmetry here is informative: crypto retail is structurally long-biased, so if any
    discount exists it should be larger on the Sell side.
    """
    out = {}
    for d, g in liq.groupby("direction"):
        a = g["adverse_bps"].to_numpy(dtype=float)
        n = g["usd_value"].to_numpy(dtype=float)
        out[d] = {
            "n": int(len(a)),
            "who_was_liquidated": "LONG" if d == "Sell" else "SHORT",
            "wmedian_bps": round(_wmedian(a, n), 2),
            "median_bps": round(float(np.median(a)), 2),
            "pct_adverse": round(float((a > 0).mean()), 3),
        }
    return out
