"""Baselines your strategy MUST beat, net of costs.

If the AI can't beat buy-and-hold after fees, it's a negative result — measure
against these every run (agent-backtest-lab `baselines/`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def buy_and_hold(prices: pd.Series) -> pd.Series:
    return prices.pct_change().fillna(0.0)


def naive_momentum(prices: pd.Series, lookback: int = 20) -> pd.Series:
    signal = np.sign(prices.pct_change(lookback)).shift(1).fillna(0.0)
    return signal * prices.pct_change().fillna(0.0)


def mean_reversion(prices: pd.Series, lookback: int = 20) -> pd.Series:
    z = (prices - prices.rolling(lookback).mean()) / prices.rolling(lookback).std()
    signal = (-np.sign(z)).shift(1).fillna(0.0)
    return signal * prices.pct_change().fillna(0.0)


def random_baseline(prices: pd.Series, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    signal = pd.Series(rng.choice([-1, 0, 1], len(prices)), index=prices.index).shift(1).fillna(0.0)
    return signal * prices.pct_change().fillna(0.0)


def run_baselines(prices: pd.Series, seed: int = 0) -> dict[str, pd.Series]:
    return {
        "buy_and_hold": buy_and_hold(prices),
        "naive_momentum": naive_momentum(prices),
        "mean_reversion": mean_reversion(prices),
        "random": random_baseline(prices, seed),
    }
