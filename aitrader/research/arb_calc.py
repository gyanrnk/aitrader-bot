"""Net-of-cost analysis for cross-exchange funding arbitrage — the HONEST way.

STATUS: the strategy this file analyses was REJECTED 2026-07-17 (registry: `xexch_arb`).
The file is kept because the *analysis* is reusable and because two of its original bugs
are worth preserving as a warning. Read `persistence()` before trusting `analyze()`.

The trap this file was written to avoid: entry/exit cost is a ONE-TIME fee. Annualising it
over a short data window makes it look enormous. The right questions are:
  1. GROSS APR — the funding spread you earn while positioned.
  2. BREAKEVEN HOLD — how many days you must hold for the accrued spread to cover the
     one-time round-trip cost.
  3. NET APR — depends on how long you actually hold. If a wide spread persists and you
     hold long, cost amortises toward zero. If it flips fast and you churn, cost dominates.

So profitability hinges on SPREAD PERSISTENCE. That was the open question. IT IS NOW
ANSWERED, AND THE ANSWER IS NO — see `persistence()`.

--------------------------------------------------------------------------------------
TWO BUGS THIS FILE ORIGINALLY HAD. Both flattered the strategy. Both are fixed below.

BUG 1 — no availability multiplier.
    `net_at()` computed `gross_apr - annual_cost`, which silently assumes you are
    positioned 100% of the time. You are not: SOL's spread cleared the 6% entry on only
    70% of polls. Idle capital earns nothing. SOL's headline "6.7% on capital" was really
    ~4.7%. An APR you only earn 70% of the time is not that APR.

BUG 2 — a hold assumption contradicted by the data.
    `net_at(30)` reported +13.4% APR for SOL by assuming a 30-DAY hold. The longest wide
    spread ever observed was 13.8 HOURS. The number was arithmetically correct and
    economically fiction. A hold period is not a parameter you choose — it is a fact the
    market decides, and it must be MEASURED, not assumed.

The general lesson (see also RESEARCH_GUIDE.md): a formula can be right in every step and
still answer a question reality never asked. `analyze()` now refuses to report a net APR
for a hold period longer than the observed spread life.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def persistence(xfunding: pd.DataFrame, enter_pct: float = 6.0,
                round_trip_cost_pct: float = 0.32) -> dict:
    """THE decisive test: once a spread is wide, does it STAY wide past breakeven?

    This is what actually decides the strategy, and it needs no model — just the tape.
    An "episode" is a contiguous run of polls with spread > enter_pct.

    Verdict 2026-07-17 on 51h / 1036 polls: 42 episodes, ZERO survived to breakeven.
    Longest episode 13.8h vs 163h needed. Short by 12x.
    """
    out = {}
    for coin, g in xfunding.groupby("coin"):
        g = g.sort_values("ts")
        s = g["spread_pct"].to_numpy(dtype=float)
        t = pd.to_datetime(g["ts"]).to_numpy()
        gross_apr = float(s[s > enter_pct].mean()) if (s > enter_pct).any() else 0.0
        breakeven_h = (round_trip_cost_pct / (gross_apr / 365.0) * 24) if gross_apr > 0 else float("inf")

        runs, i = [], 0
        wide = s > enter_pct
        while i < len(wide):
            if wide[i]:
                j = i
                while j + 1 < len(wide) and wide[j + 1]:
                    j += 1
                runs.append((t[j] - t[i]) / np.timedelta64(1, "h"))
                i = j + 1
            else:
                i += 1
        runs = np.array(runs) if runs else np.array([0.0])
        # each change of the short/long venue pair is a fresh round trip on BOTH legs
        flips = int((g["short_on"] != g["short_on"].shift()).sum())

        survivors = int((runs > breakeven_h).sum()) if np.isfinite(breakeven_h) else 0
        out[coin] = {
            "episodes": int(len(runs)) if runs.any() else 0,
            "median_life_h": round(float(np.median(runs)), 2),
            "max_life_h": round(float(runs.max()), 2),
            "breakeven_h": round(breakeven_h, 1) if np.isfinite(breakeven_h) else None,
            "survived_to_breakeven": survivors,
            "shortfall_x": (round(breakeven_h / runs.max(), 1)
                            if runs.max() > 0 and np.isfinite(breakeven_h) else None),
            "leg_flips": flips,
            "verdict": ("CAPTURABLE" if survivors > 0 else
                        "DEAD — spread never lives long enough to amortise the round trip"),
        }
    return out


def analyze(xfunding: pd.DataFrame, enter_pct: float = 6.0,
            round_trip_cost_pct: float = 0.32) -> dict:
    """round_trip_cost_pct = open+close both legs (default 0.32% = 4 legs x 8bps).

    Reports net APR ONLY for hold periods the data actually supports (BUG 2), and always
    multiplies by availability (BUG 1).
    """
    persist = persistence(xfunding, enter_pct, round_trip_cost_pct)
    out = {}
    for coin, g in xfunding.groupby("coin"):
        s = g.sort_values("ts")["spread_pct"].to_numpy(dtype=float)
        wide = s[s > enter_pct]
        avail = len(wide) / len(s) if len(s) else 0.0        # share of time a trade exists
        gross_apr = float(wide.mean()) if len(wide) else 0.0  # yield WHILE POSITIONED
        daily = gross_apr / 365.0
        breakeven_days = round_trip_cost_pct / daily if daily > 0 else float("inf")
        max_life_days = persist[coin]["max_life_h"] / 24.0

        def net_at(hold_days: float):
            """Net APR on NOTIONAL for a given hold. None if the data can't support it."""
            if hold_days <= 0 or gross_apr == 0:
                return 0.0
            if hold_days > max_life_days:
                return None          # BUG 2: refuse to price a hold longer than observed life
            annual_cost = round_trip_cost_pct * 365.0 / hold_days
            return round((gross_apr - annual_cost) * avail, 2)     # BUG 1: availability

        # the longest hold the tape actually justifies
        realistic = net_at(max_life_days) if max_life_days > 0 else 0.0
        out[coin] = {
            "gross_apr_while_positioned": round(gross_apr, 1),
            "availability": round(avail, 2),
            "breakeven_days": round(breakeven_days, 1) if np.isfinite(breakeven_days) else None,
            "max_observed_hold_days": round(max_life_days, 2),
            "net_apr_at_max_observed_hold": realistic,
            "net_on_capital_at_max_hold": (None if realistic is None
                                           else round(realistic / 2, 2)),  # ~2x capital tied
            "net_apr_hold_7d": net_at(7),      # None => data does not support this hold
            "net_apr_hold_30d": net_at(30),    # None => the old headline number was fiction
            "persistence": persist[coin],
        }
    return out
