"""Stage 3 — net-of-cost backtest of the delta-neutral funding-carry strategy.

Economic mechanism (NOT a price prediction):
  Hold LONG spot + SHORT perp (delta-neutral: price move cancels). When funding > 0,
  the perp shorts RECEIVE funding from longs — a real recurring cash flow. We collect
  it while funding stays above cost, and step aside when it doesn't.

Pre-registered rule (chosen from economics, NOT scanned — keeps trials = 1):
  * enter when funding > entry_thresh, exit when funding < exit_thresh (hysteresis
    so we don't churn and bleed fees).
Costs are pessimistic: two legs (spot + perp) each way, taker + half-spread, plus a
small per-period basis/borrow drag. Every number reported is NET.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .funding_data import fetch_funding, PERIODS_PER_YEAR

# --- pre-registered params (economic, not data-mined) ---
ENTRY_THRESH = 0.0001      # 1 bp / 8h  (~11% annualized) — must clear cost to bother
EXIT_THRESH = 0.0           # step aside when funding turns non-positive
ONE_WAY_COST = 0.0015       # 15 bp to open OR close the 2-leg delta-neutral position
HOLDING_DRAG = 0.00002      # 0.2 bp/period basis+borrow noise (pessimistic)


def carry_net_returns(funding: pd.Series,
                      entry: float = ENTRY_THRESH, exit: float = EXIT_THRESH,
                      one_way_cost: float = ONE_WAY_COST,
                      holding_drag: float = HOLDING_DRAG) -> pd.Series:
    """Per-8h NET return series for the carry strategy on one symbol."""
    pos = np.zeros(len(funding))
    state = 0
    f = funding.to_numpy()
    for i in range(1, len(f)):
        # decide using funding known at the PREVIOUS print (point-in-time)
        if state == 0 and f[i - 1] > entry:
            state = 1
        elif state == 1 and f[i - 1] < exit:
            state = 0
        pos[i] = state
    pos_s = pd.Series(pos, index=funding.index)
    # funding received while in position, minus drag; minus cost on each transition
    gross = pos_s * (funding - holding_drag)
    turnover = pos_s.diff().abs().fillna(pos_s.abs())
    cost = turnover * one_way_cost
    return gross - cost


def _sharpe(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR))


def backtest_symbol(symbol: str, years: float = 2.0) -> dict:
    funding = fetch_funding(symbol, years=years)["funding"]
    net = carry_net_returns(funding)
    ann_return = float(net.mean() * PERIODS_PER_YEAR)
    equity = (1 + net.fillna(0)).cumprod()
    dd = float(((equity - equity.cummax()) / equity.cummax()).min())
    time_in = float((net != 0).mean())
    return {
        "symbol": symbol,
        "n_periods": int(len(net)),
        "net_sharpe": round(_sharpe(net), 3),
        "net_apr": round(ann_return, 4),          # annualized net return
        "max_drawdown": round(dd, 4),
        "time_in_market": round(time_in, 3),
        "avg_funding_bps": round(float(funding.mean() * 1e4), 3),
        "_net": net,                                # kept for pooling
    }


def backtest_portfolio(symbols: list[str], years: float = 2.0) -> dict:
    rows = [backtest_symbol(s, years) for s in symbols]
    # equal-weight pooled net returns across symbols (aligned on time)
    pooled = pd.concat([r["_net"] for r in rows], axis=1).mean(axis=1)
    for r in rows:
        r.pop("_net", None)
    sharpes = [r["net_sharpe"] for r in rows if r["net_sharpe"] == r["net_sharpe"]]
    return {
        "per_symbol": rows,
        "pooled_net_sharpe": round(_sharpe(pooled), 3),
        "pooled_n_periods": int(len(pooled)),
        "pct_symbols_positive": round(sum(s > 0 for s in sharpes) / max(len(sharpes), 1), 2),
        "mean_symbol_sharpe": round(float(np.mean(sharpes)), 3) if sharpes else None,
    }
