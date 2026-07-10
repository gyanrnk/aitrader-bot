"""Deterministic synthetic OHLCV so the whole system runs with no network/keys.

Generates a geometric-Brownian-motion price with a mild regime shift, enough to
exercise indicators, agents, backtest and discipline checks reproducibly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class MockProvider:
    def __init__(self, seed: int = 42):
        self.seed = seed

    def ohlcv(self, symbol: str, lookback: int = 400) -> pd.DataFrame:
        # symbol-stable seed so each ticker has its own repeatable path
        rng = np.random.default_rng(self.seed + (abs(hash(symbol)) % 10_000))
        n = lookback
        mu, sigma = 0.0004, 0.02
        # regime shift halfway through to create trend + reversal
        drift = np.concatenate([np.full(n // 2, mu), np.full(n - n // 2, -mu / 2)])
        rets = rng.normal(drift, sigma)
        close = 100 * np.exp(np.cumsum(rets))
        high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
        low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
        open_ = np.concatenate([[close[0]], close[:-1]])
        vol = rng.integers(1_000_000, 5_000_000, n).astype(float)
        idx = pd.date_range(end=pd.Timestamp("2026-07-09"), periods=n, freq="B")
        return pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
            index=idx,
        )
