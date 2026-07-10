"""Time-series momentum (TSMOM) — research candidate #2.

Rule (economically: trend persistence; this is a PREDICTION, not a cash flow, so it
MUST survive brutal costs): go long when the past `lookback`-day return is positive,
short when negative, next-bar return, costs on every position change.

Works on a RETURN series so the falsification audit can shuffle returns to destroy the
trend structure and prove the edge isn't just autocorrelation-luck.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Settings
from ..data import get_provider

PERIODS_PER_YEAR = 365   # crypto trades daily, 24/7
COST_PER_SIDE = 0.0010   # 10 bp per side (pessimistic retail taker+spread)


def tsmom_from_returns(ret: pd.Series, lookback: int = 30,
                       cost: float = COST_PER_SIDE) -> pd.Series:
    """Per-day NET return of TSMOM given a daily return series."""
    signal = np.sign(ret.rolling(lookback).sum()).shift(1).fillna(0.0)  # point-in-time
    strat = signal * ret
    turnover = signal.diff().abs().fillna(signal.abs())
    return strat - turnover * cost


def tsmom_net_returns(close: pd.Series, lookback: int = 30,
                      cost: float = COST_PER_SIDE) -> pd.Series:
    return tsmom_from_returns(close.pct_change().fillna(0.0), lookback, cost)


def load_prices(symbols: list[str], lookback: int = 900) -> dict[str, pd.Series]:
    prov = get_provider(Settings(data_provider="yfinance"))
    out = {}
    for s in symbols:
        try:
            out[s] = prov.ohlcv(s, lookback=lookback)["close"]
        except Exception:
            continue
    return out
