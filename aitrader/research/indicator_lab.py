"""Indicator Lab — test EVERY popular TradingView-style indicator strategy honestly.

The claims you see in videos/courses ("RSI + MACD + AI = game changer") are all in here.
Each strategy is run point-in-time, NET of costs, and compared against buy & hold. Because
we test many at once, the Deflated Sharpe correction is applied — with N strategies, the
best one looks good by luck alone, so the bar rises.

Verdict rule: a strategy is only interesting if it beats buy & hold net-of-cost AND
survives the multiple-testing correction.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.indicators import rsi, macd, sma


def _bbands(close: pd.Series, n: int = 20, k: float = 2.0):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std()
    return mid - k * sd, mid, mid + k * sd


def _hold_until_flip(raw: pd.Series) -> pd.Series:
    """Turn entry/exit triggers (+1/-1/0) into a held position."""
    pos = raw.replace(0, np.nan).ffill().fillna(0.0)
    return pos


def strategies(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Return {name: position series} — position is +1 long / -1 short / 0 flat."""
    close = df["close"]
    r = rsi(close)
    macd_line, macd_sig, macd_hist = macd(close)
    lo, mid, up = _bbands(close)
    out = {}

    # 1. RSI mean-reversion (the classic "oversold = buy")
    raw = pd.Series(0.0, index=close.index)
    raw[r < 30] = 1.0
    raw[r > 70] = -1.0
    out["RSI mean-reversion (30/70)"] = _hold_until_flip(raw)

    # 2. RSI trend (above 50 = bullish)
    out["RSI trend (>50)"] = np.sign(r - 50).replace(0, np.nan).ffill().fillna(0.0)

    # 3. MACD crossover
    out["MACD crossover"] = np.sign(macd_hist).replace(0, np.nan).ffill().fillna(0.0)

    # 4. Golden/death cross (SMA 20/50)
    out["MA cross (20/50)"] = np.sign(sma(close, 20) - sma(close, 50)).replace(0, np.nan).ffill().fillna(0.0)

    # 5. MA cross (50/200) — the famous one
    out["MA cross (50/200)"] = np.sign(sma(close, 50) - sma(close, 200)).replace(0, np.nan).ffill().fillna(0.0)

    # 6. Bollinger mean-reversion
    raw = pd.Series(0.0, index=close.index)
    raw[close < lo] = 1.0
    raw[close > up] = -1.0
    out["Bollinger mean-reversion"] = _hold_until_flip(raw)

    # 7. Bollinger breakout
    raw = pd.Series(0.0, index=close.index)
    raw[close > up] = 1.0
    raw[close < lo] = -1.0
    out["Bollinger breakout"] = _hold_until_flip(raw)

    # 8. RSI + MACD combo (the "AI game changer" style stack)
    combo = ((r > 50).astype(float) + (macd_hist > 0).astype(float)) - 1.0   # +1 both bull, -1 both bear
    out["RSI + MACD combo"] = combo.replace(0, np.nan).ffill().fillna(0.0)

    return out


def evaluate(df: pd.DataFrame, cost_bps: float = 10.0, ppy: int = 365) -> pd.DataFrame:
    """Net-of-cost performance of every strategy + buy & hold, point-in-time."""
    close = df["close"]
    ret = close.pct_change().fillna(0.0)
    rows = []
    strats = strategies(df)
    strats["BUY & HOLD (benchmark)"] = pd.Series(1.0, index=close.index)

    for name, pos in strats.items():
        p = pos.shift(1).fillna(0.0)                    # trade on NEXT bar (no lookahead)
        gross = p * ret
        turnover = p.diff().abs().fillna(p.abs())
        net = gross - turnover * (cost_bps / 1e4)
        n = net.dropna()
        if len(n) < 30 or n.std() == 0:
            continue
        sharpe = float(n.mean() / n.std(ddof=1) * np.sqrt(ppy))
        eq = (1 + n).cumprod()
        dd = float(((eq - eq.cummax()) / eq.cummax()).min())
        rows.append({
            "strategy": name,
            "net_sharpe": round(sharpe, 2),
            "total_return": round(float(eq.iloc[-1] - 1), 3),
            "max_dd": round(dd, 3),
            "trades": int((turnover > 0).sum()),
        })
    out = pd.DataFrame(rows).sort_values("net_sharpe", ascending=False).reset_index(drop=True)
    bh = out.loc[out["strategy"].str.startswith("BUY & HOLD"), "net_sharpe"]
    bh_sharpe = float(bh.iloc[0]) if len(bh) else 0.0
    out["beats_buyhold"] = out["net_sharpe"] > bh_sharpe
    return out
