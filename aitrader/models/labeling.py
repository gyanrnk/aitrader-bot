"""Triple-barrier labeling (López de Prado, 'Advances in Financial ML').

For each bar, set three barriers over the next `horizon` bars:
  * upper = +profit_mult * volatility   -> label +1 (up move hit first)
  * lower = -stop_mult   * volatility   -> label  0 (down move hit first)
  * time  = horizon bars                -> label by sign of terminal return

Why this beats naive "next-day up/down": it labels what a *risk-managed trade*
would actually experience (which barrier is touched first), so the model learns
tradable moves, not noise. Volatility-scaled barriers adapt to regime.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def triple_barrier_labels(
    close: pd.Series,
    horizon: int = 5,
    profit_mult: float = 1.5,
    stop_mult: float = 1.0,
    vol_window: int = 20,
) -> pd.Series:
    """Return a Series of {1: up, 0: down} aligned to `close` (NaN where undefined)."""
    ret = close.pct_change()
    vol = ret.rolling(vol_window).std()
    labels = pd.Series(index=close.index, dtype="float64")

    prices = close.to_numpy()
    v = vol.to_numpy()
    n = len(prices)
    for i in range(n - 1):
        sigma = v[i]
        if not np.isfinite(sigma) or sigma <= 0:
            continue
        up = prices[i] * (1 + profit_mult * sigma)
        dn = prices[i] * (1 - stop_mult * sigma)
        end = min(i + horizon, n - 1)
        label = 1 if prices[end] >= prices[i] else 0   # time-barrier fallback
        for j in range(i + 1, end + 1):
            if prices[j] >= up:
                label = 1
                break
            if prices[j] <= dn:
                label = 0
                break
        labels.iloc[i] = label
    return labels
