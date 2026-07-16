"""Net-of-cost analysis for cross-exchange funding arbitrage — the HONEST way.

The trap: entry/exit cost is a ONE-TIME fee. Annualizing it over a short data window
makes it look enormous. The right questions are:
  1. GROSS APR — the funding spread you earn while positioned.
  2. BREAKEVEN HOLD — how many days you must hold for the accrued spread to cover the
     one-time round-trip cost.
  3. NET APR — depends on how long you actually hold (turnover). If a wide spread
     persists and you hold long, cost amortizes toward zero and net -> gross. If it
     flips fast and you churn, cost dominates and net goes negative.

So profitability hinges on SPREAD PERSISTENCE (do wide spreads last past breakeven?),
which needs weeks of data to know. On DEPLOYED capital, halve the notional yield
(unleveraged you tie up ~2x notional across the two exchanges).
"""
from __future__ import annotations

import pandas as pd


def analyze(xfunding: pd.DataFrame, enter_pct: float = 6.0,
            round_trip_cost_pct: float = 0.32) -> dict:
    """round_trip_cost_pct = open+close both legs (default 0.32% = 4 legs x 8bps)."""
    out = {}
    for coin, g in xfunding.groupby("coin"):
        s = g.sort_values("ts")["spread_pct"].to_numpy()
        wide = s[s > enter_pct]
        avail = len(wide) / len(s) if len(s) else 0.0        # % of time a tradeable spread exists
        gross_apr = float(wide.mean()) if len(wide) else 0.0  # yield while positioned
        daily = gross_apr / 365.0
        breakeven_days = round_trip_cost_pct / daily if daily > 0 else float("inf")
        # net APR if you hold each position for H days (cost amortized over H):
        def net_at(hold_days):
            if hold_days <= 0 or gross_apr == 0:
                return 0.0
            annual_cost = round_trip_cost_pct * 365.0 / hold_days
            return round(gross_apr - annual_cost, 2)
        out[coin] = {
            "gross_apr": round(gross_apr, 1),
            "availability": round(avail, 2),
            "breakeven_days": round(breakeven_days, 1) if breakeven_days != float("inf") else None,
            "net_apr_hold_7d": net_at(7),
            "net_apr_hold_30d": net_at(30),
            "net_on_capital_hold_30d": round(net_at(30) / 2, 2),   # ~2x capital tied up
        }
    return out
