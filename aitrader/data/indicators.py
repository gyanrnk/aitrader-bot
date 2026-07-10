"""Feature layer: technical indicators computed with plain numpy/pandas.

Kept dependency-free (no TA-Lib/pandas-ta required) so the whole pipeline runs
anywhere. These are the numeric features the analyst agents reason over.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig  # macd, signal, histogram


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period).mean()


def compute_features(df: pd.DataFrame) -> dict[str, float]:
    """Snapshot of indicators at the LAST row of `df` (already point-in-time)."""
    close = df["close"]
    macd_line, macd_sig, macd_hist = macd(close)
    atr_series = atr(df)
    last = -1
    price = float(close.iloc[last])
    return {
        "price": price,
        "rsi14": float(rsi(close).iloc[last]),
        "macd_hist": float(macd_hist.iloc[last]),
        "sma20": float(sma(close, 20).iloc[last]),
        "sma50": float(sma(close, 50).iloc[last]),
        "trend": float(close.iloc[last] / close.iloc[max(last - 20, -len(close))] - 1),
        "atr_pct": float(atr_series.iloc[last] / price) if price else 0.0,
        "vol_20d": float(close.pct_change().rolling(20).std().iloc[last]),
    }
