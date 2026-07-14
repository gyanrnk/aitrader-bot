"""Delta-neutral funding-carry — the REAL profit mechanism (forward paper, fake money).

Unlike the directional signal (which guesses up/down and has no edge), this is
market-neutral: for each crypto with POSITIVE funding, hold long-spot + short-perp and
just COLLECT the funding payment each period. Price moves cancel; you earn the funding.
This is a real cash flow, the one edge with genuine economic basis.

Honest: the edge is SMALL (funding is tiny) — realistically low single digits/yr
unleveraged. But it's real and defensible, not a prediction. Forward-only, net of cost.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data" / "carry_state.json"
EQUITY = ROOT / "data" / "carry_equity.csv"

START = 10_000.0
MAX_WEIGHT = 0.25        # up to 25% of capital per coin in a carry position
ENTER_ABOVE = 2e-6       # only carry when hourly funding clears this (covers cost over time)
ONE_WAY_COST = 0.0015    # 15 bp to open/close the 2-leg delta-neutral position
PERIOD_HR = 10 / 60.0    # snapshots are ~10 min apart


def _load() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"equity": START, "weights": {}}


def step(history: pd.DataFrame) -> dict:
    if history.empty:
        return {"note": "no data"}
    latest = history.sort_values("ts").groupby("symbol").tail(1)
    # crypto only (funding != 0); funding is hourly, normalized (rate/price)
    fund = {r["symbol"]: float(r["funding"]) for _, r in latest.iterrows()
            if float(r["funding"]) != 0.0}
    if not fund:
        return {"note": "no funding data yet"}

    st = _load()
    equity = float(st["equity"])
    weights = {k: float(v) for k, v in st.get("weights", {}).items()}

    # 1. EARN funding on positions held into this period (delta-neutral: price cancels)
    earned = sum(weights.get(s, 0.0) * f * PERIOD_HR for s, f in fund.items())
    equity *= (1 + earned)

    # 2. rebalance WITH HYSTERESIS to avoid churn: enter only when funding clears the
    #    threshold, but stay in until funding actually turns non-positive. This is the
    #    key fix — flip-flopping around a single threshold bleeds cost.
    turnover = 0.0
    new_w = {}
    for s, f in fund.items():
        prev = weights.get(s, 0.0)
        if prev > 0:
            tgt = MAX_WEIGHT if f > 0 else 0.0          # hold until funding goes negative
        else:
            tgt = MAX_WEIGHT if f > ENTER_ABOVE else 0.0  # enter only on clear positive
        turnover += abs(tgt - prev)
        new_w[s] = tgt
    equity *= (1 - turnover * ONE_WAY_COST)

    ts = history["ts"].max()
    STATE.write_text(json.dumps({"equity": equity, "weights": new_w}, indent=2))
    n_active = sum(1 for w in new_w.values() if w > 0)
    pd.DataFrame([{"ts": ts.isoformat(), "equity": round(equity, 2),
                   "active": n_active}]).to_csv(
        EQUITY, mode="a", header=not EQUITY.exists(), index=False)

    return {"equity": round(equity, 2), "pnl_pct": round((equity / START - 1) * 100, 3),
            "active_carry": n_active,
            "apr_annualized": round(earned * (365 * 24 / (PERIOD_HR)) * 100, 2) if earned else 0.0}
