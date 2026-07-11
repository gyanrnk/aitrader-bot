"""Forward paper-trading with FAKE money on LIVE data — the honest real test.

Each cycle: mark positions to the latest live prices, act on the current signals with
fake money, and log the equity. Forward-only (no lookahead), free, no broker account.
Over weeks the equity curve shows whether the signals actually make money live — the one
test that can't be curve-fit.

Signed-units accounting handles longs and shorts:
  cash -= delta_units * price + cost ;  equity = cash + sum(units * price)
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data" / "paper_state.json"
EQUITY = ROOT / "data" / "paper_equity.csv"

START_EQUITY = 10_000.0
RISK_FRAC = 0.15          # target weight per active signal (fraction of equity)
COST_BPS = 5.0            # per-side cost


def _load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"cash": START_EQUITY, "units": {}, "start_equity": START_EQUITY}


def mark_and_trade(history: pd.DataFrame, analytics) -> dict:
    """Advance the paper portfolio one step using the latest snapshot + signals."""
    if history.empty:
        return {"note": "no data"}
    latest = history.sort_values("ts").groupby("symbol").tail(1)
    prices = {r["symbol"]: float(r["price"]) for _, r in latest.iterrows()}

    st = _load_state()
    cash = float(st["cash"])
    units = {k: float(v) for k, v in st.get("units", {}).items()}

    # equity BEFORE trading (mark to market)
    equity = cash + sum(units.get(s, 0.0) * prices.get(s, 0.0) for s in prices)
    if equity <= 0:
        equity = START_EQUITY  # safety

    # act on current signals
    n_active = 0
    for sym, g in history.groupby("symbol"):
        sig = analytics.compute_signal(g)
        price = prices.get(sym)
        if not sig or price is None:
            continue
        tgt_w = RISK_FRAC if sig["signal"] == "UP" else -RISK_FRAC if sig["signal"] == "DOWN" else 0.0
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
    ts = history["ts"].max()

    # persist
    STATE.write_text(json.dumps({"cash": cash, "units": units,
                                 "start_equity": st["start_equity"]}, indent=2))
    row = pd.DataFrame([{"ts": ts.isoformat(), "equity": round(equity, 2),
                         "cash": round(cash, 2), "active_positions": n_active}])
    row.to_csv(EQUITY, mode="a", header=not EQUITY.exists(), index=False)

    pnl = equity / st["start_equity"] - 1
    return {"equity": round(equity, 2), "pnl_pct": round(pnl * 100, 3),
            "active_positions": n_active}
