"""Feature engineering. Predictive features matter more than the model.

All features are computed from data available AT each bar (no lookahead): every
column at row t uses only information through t. Returns a feature matrix aligned
to the price index.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.indicators import rsi, macd, atr, sma


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV -> engineered feature matrix (point-in-time safe)."""
    close = df["close"]
    ret1 = close.pct_change()
    macd_line, macd_sig, macd_hist = macd(close)
    atr14 = atr(df)

    feats = pd.DataFrame(index=df.index)
    # momentum / trend
    feats["ret_1"] = ret1
    feats["ret_5"] = close.pct_change(5)
    feats["ret_10"] = close.pct_change(10)
    feats["ret_20"] = close.pct_change(20)
    feats["sma_ratio"] = sma(close, 10) / sma(close, 50) - 1.0
    feats["px_vs_sma20"] = close / sma(close, 20) - 1.0
    # oscillators
    feats["rsi_14"] = rsi(close) / 100.0
    feats["macd_hist"] = macd_hist / close            # scale-free
    # volatility / range
    feats["vol_10"] = ret1.rolling(10).std()
    feats["vol_20"] = ret1.rolling(20).std()
    feats["atr_pct"] = atr14 / close
    # volume
    feats["vol_chg"] = df["volume"].pct_change().clip(-3, 3)
    feats["vol_z"] = (
        (df["volume"] - df["volume"].rolling(20).mean())
        / df["volume"].rolling(20).std()
    )
    # lagged returns (short memory)
    for lag in (1, 2, 3):
        feats[f"ret_lag_{lag}"] = ret1.shift(lag)

    return feats.replace([np.inf, -np.inf], np.nan)


FEATURE_COLUMNS = [
    "ret_1", "ret_5", "ret_10", "ret_20", "sma_ratio", "px_vs_sma20",
    "rsi_14", "macd_hist", "vol_10", "vol_20", "atr_pct", "vol_chg", "vol_z",
    "ret_lag_1", "ret_lag_2", "ret_lag_3",
]
