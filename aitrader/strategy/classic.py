"""The two classic strategies: MA crossover and RSI mean-reversion.

Implemented because "we measured it and it failed" is a far stronger statement than "we
never built it". Both are the standard starting point for a systematic trading project,
and both belong to families we have already tested here:

  MA crossover     -> trend following. Same family as `tsmom`, which scored 3/6 on the
                     Stage-4 gauntlet: PBO 0.76, DSR 0, falsification p=0.15.
  RSI reversion    -> the mean-reversion side of the same coin. Our directional signal
                     engine ran 2,930 live forward predictions at a 49.9% hit rate,
                     95% CI [48.1%, 51.7%] — a coin flip, measured not assumed.

So the expectation going in is failure. Run them anyway: a documented negative on OUR
data is worth more than an inherited belief, and it keeps the interface honest by proving
it can carry a real strategy end to end.

NOTE the `describe()` bodies. Neither can name who pays them, so both auto-fail the
napkin test at R0 before producing a single signal. That is the interface working: the
filter fires at definition time, not after a week of backtesting.
"""
from __future__ import annotations

import pandas as pd

from ..data.indicators import rsi, sma
from ..research.napkin import Idea
from .base import Signal, Strategy, _now


class MACrossover(Strategy):
    """Long when fast SMA is above slow SMA, flat/short otherwise."""

    def __init__(self, fast: int = 50, slow: int = 200, allow_short: bool = False):
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be < slow ({slow})")
        self.fast, self.slow, self.allow_short = fast, slow, allow_short
        self.name = f"ma_cross_{fast}_{slow}"

    def describe(self) -> Idea:
        return Idea(
            name=self.name,
            # Deliberately empty: there is no answer. A moving average crossing another
            # moving average does not oblige anybody to pay me. R0 fires here.
            mechanism="",
            edge_bps=0.0,
            cost_bps=10.0,          # retail round trip on a liquid perp, spread included
            trades_per_year=50,
            capacity_usd=100_000,
            barrier="",             # none — it is two lines of pandas, universally known
            notes="Trend following. Same family as tsmom (gauntlet 3/6, PBO 0.76).",
        )

    def signal(self, df: pd.DataFrame) -> Signal:
        close = df["close"]
        price = float(close.iloc[-1])
        if len(close) < self.slow + 1:
            return Signal("HOLD", 0.0, f"warmup: need {self.slow + 1} bars, have {len(close)}",
                          price, _now())

        f, s = sma(close, self.fast), sma(close, self.slow)
        f_now, s_now = float(f.iloc[-1]), float(s.iloc[-1])
        f_prev, s_prev = float(f.iloc[-2]), float(s.iloc[-2])
        if pd.isna(f_now) or pd.isna(s_now) or s_now == 0:
            return Signal("HOLD", 0.0, "indicator not ready", price, _now())

        # Separation as a fraction of the slow MA — a proxy for how decisive the state is.
        # It is NOT a probability; see the warning in Strategy.signal.
        gap = abs(f_now - s_now) / s_now
        conf = float(min(1.0, gap * 20))

        crossed_up = f_prev <= s_prev and f_now > s_now
        crossed_dn = f_prev >= s_prev and f_now < s_now
        if crossed_up:
            return Signal("BUY", conf, f"MA{self.fast} crossed above MA{self.slow}", price, _now())
        if crossed_dn:
            act = "SELL" if self.allow_short else "HOLD"
            return Signal(act, conf, f"MA{self.fast} crossed below MA{self.slow}", price, _now())
        if f_now > s_now:
            return Signal("BUY", conf, f"MA{self.fast} above MA{self.slow} (holding trend)",
                          price, _now())
        return Signal("SELL" if self.allow_short else "HOLD", conf,
                      f"MA{self.fast} below MA{self.slow}", price, _now())


class RSIReversion(Strategy):
    """Buy oversold, sell overbought — the textbook mean-reversion rule."""

    def __init__(self, period: int = 14, low: float = 30.0, high: float = 70.0,
                 allow_short: bool = False):
        if not 0 < low < high < 100:
            raise ValueError(f"need 0 < low ({low}) < high ({high}) < 100")
        self.period, self.low, self.high = period, low, high
        self.allow_short = allow_short
        self.name = f"rsi_rev_{period}_{int(low)}_{int(high)}"

    def describe(self) -> Idea:
        return Idea(
            name=self.name,
            # Also empty, and for the same reason. "It bounced from 30 before" is a
            # pattern, not a mechanism. RESEARCH_GUIDE.md's first red flag.
            mechanism="",
            edge_bps=0.0,
            cost_bps=10.0,
            trades_per_year=150,    # reverts more often than a trend flips
            capacity_usd=100_000,
            barrier="",             # none — shipped in every retail charting tool
            notes="Mean reversion. Our directional engine measured 49.9% over 2,930 "
                  "forward predictions.",
        )

    def signal(self, df: pd.DataFrame) -> Signal:
        close = df["close"]
        price = float(close.iloc[-1])
        if len(close) < self.period + 2:
            return Signal("HOLD", 0.0,
                          f"warmup: need {self.period + 2} bars, have {len(close)}", price, _now())

        r = float(rsi(close, self.period).iloc[-1])
        if pd.isna(r):
            return Signal("HOLD", 0.0, "RSI not ready", price, _now())

        if r <= self.low:
            conf = float(min(1.0, (self.low - r) / max(self.low, 1e-9)))
            return Signal("BUY", conf, f"RSI {r:.1f} <= {self.low} (oversold)", price, _now())
        if r >= self.high:
            conf = float(min(1.0, (r - self.high) / max(100 - self.high, 1e-9)))
            act = "SELL" if self.allow_short else "HOLD"
            return Signal(act, conf, f"RSI {r:.1f} >= {self.high} (overbought)", price, _now())
        return Signal("HOLD", 0.0, f"RSI {r:.1f} in neutral band "
                                   f"({self.low}-{self.high})", price, _now())


REGISTRY = {"ma_cross": MACrossover, "rsi_reversion": RSIReversion}
