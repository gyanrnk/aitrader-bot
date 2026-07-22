"""Forward paper-trading with FAKE money on LIVE data — the honest real test.

Tracks TWO equity curves so the comparison is meaningful:
  * strategy  — trades the current signals with fake money
  * buy&hold  — equal-weight the coins once and just hold (the benchmark to beat)

If the strategy line can't beat the buy&hold line, the signals add no value — that is
the single most honest question this whole project answers. Forward-only, free.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data" / "paper_state.json"
EQUITY = ROOT / "data" / "paper_equity.csv"

START_EQUITY = 10_000.0
RISK_FRAC = 0.15
COST_BPS = 5.0


def _load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"cash": START_EQUITY, "units": {}, "start_equity": START_EQUITY, "bh_units": {}}


def mark_and_trade(history: pd.DataFrame, analytics) -> dict:
    if history.empty:
        return {"note": "no data"}
    latest = history.sort_values("ts").groupby("symbol").tail(1)
    prices = {r["symbol"]: float(r["price"]) for _, r in latest.iterrows()}

    st = _load_state()
    cash = float(st["cash"])
    units = {k: float(v) for k, v in st.get("units", {}).items()}
    bh_units = {k: float(v) for k, v in st.get("bh_units", {}).items()}

    # initialize buy & hold ONCE: split start equity equally across the coins
    if not bh_units and prices:
        per = START_EQUITY / len(prices)
        bh_units = {s: per / p for s, p in prices.items() if p}

    equity = cash + sum(units.get(s, 0.0) * prices.get(s, 0.0) for s in prices)
    if equity <= 0:
        equity = START_EQUITY

    # --- size by MEASURED edge, not by a constant (see risk/edge_sizing.py) ----
    #
    # The old line was `tgt_w = RISK_FRAC if UP else -RISK_FRAC if DOWN else 0` — a flat
    # 0.15 per symbol with no aggregate cap, so 8 live signals meant 120% of equity. That
    # single line is the whole reason this bot ran 6.3x the volatility of buy & hold.
    #
    # Now the book is sized from the signal's OWN measured forward record. If expectancy
    # is not positive, or the hit rate is not distinguishable from a coin flip, every
    # weight is 0 — the bot declines to trade itself. That is currently the case, and it
    # is the correct answer, not a bug.
    from ..risk.edge_sizing import EdgeStats, explain, target_weights

    score = analytics.score_predictions(history)
    stats = EdgeStats(n=int(score.get("scored", 0) or 0),
                      hit_rate=float(score.get("hit_rate", 0.5) or 0.5),
                      expectancy=float(score.get("avg_return_per_call", 0.0) or 0.0))

    signals = {}
    for sym, g in history.groupby("symbol"):
        sig = analytics.compute_signal(g)
        if sig and prices.get(sym) is not None:
            signals[sym] = sig["signal"]
    weights = target_weights(signals, stats)
    sizing_note = explain(stats)

    n_active = 0
    for sym, tgt_w in weights.items():
        price = prices.get(sym)
        if price is None:
            continue
        if tgt_w != 0.0:
            n_active += 1
        tgt_units = tgt_w * equity / price
        delta = tgt_units - units.get(sym, 0.0)
        if abs(delta * price) < 1e-9:
            continue
        cost = abs(delta * price) * (COST_BPS / 1e4)
        cash -= delta * price + cost
        units[sym] = tgt_units

    equity = cash + sum(units.get(s, 0.0) * prices.get(s, 0.0) for s in prices)
    bh_equity = sum(bh_units.get(s, 0.0) * prices.get(s, 0.0) for s in prices)
    if bh_equity <= 0:
        bh_equity = START_EQUITY
    ts = history["ts"].max()

    STATE.write_text(json.dumps({"cash": cash, "units": units,
                                 "start_equity": st["start_equity"],
                                 "bh_units": bh_units}, indent=2))
    row = pd.DataFrame([{"ts": ts.isoformat(), "equity": round(equity, 2),
                         "buyhold": round(bh_equity, 2), "cash": round(cash, 2),
                         "active_positions": n_active}])
    row.to_csv(EQUITY, mode="a", header=not EQUITY.exists(), index=False)

    return {"equity": round(equity, 2), "buyhold": round(bh_equity, 2),
            "pnl_pct": round((equity / st["start_equity"] - 1) * 100, 3),
            "bh_pnl_pct": round((bh_equity / START_EQUITY - 1) * 100, 3),
            "beating_buyhold": bool(equity > bh_equity),
            "active_positions": n_active,
            "gross_exposure": round(sum(abs(w) for w in weights.values()), 3),
            "sizing": sizing_note}
