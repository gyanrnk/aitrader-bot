"""Pluggable strategy interface — one base class, concrete strategies inherit.

WHY THIS EXISTS: we accumulated 17 ad-hoc modules under `research/`, each with its own
shape (`funding_backtest`, `tsmom_backtest`, `escalation`, `delist_event`, `kraken_liq`,
`liq_dislocation`, ...). Every new idea meant writing the scaffolding again. This is the
common interface so trial #11 costs an hour, not a day.

THE DESIGN DECISION THAT MATTERS: `describe()` is ABSTRACT and returns a napkin `Idea`.
A strategy cannot be instantiated without stating WHO PAYS ME AND WHY, and WHAT BARRIER
stops this being arbed away. Our discipline stops depending on remembering to apply it —
`gate()` runs the napkin test against the strategy's own self-description, and a strategy
whose economics do not clear the bar is refused before it ever produces a signal.

TWO SHAPES, because our work genuinely has two:

  Strategy       bar-by-bar, produces BUY/HOLD/SELL. Suits trend/mean-reversion.
                 This is the classic shape — and the one we have already disproven for
                 ourselves (tsmom 3/6 on the gauntlet; 2,930 live forward predictions at
                 a 49.9% hit rate). Implemented anyway, because "we measured it" is a
                 stronger statement than "we didn't build it".

  MechanismStudy event-driven, produces a measured edge. Suits funding escalation,
                 liquidation provision, delisting. This is where our real work lives, and
                 no bar-by-bar interface fits it: there is no per-candle signal, there is
                 an episode and a number.

Both share `describe()`, because both must survive the same filter.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

import pandas as pd

from ..research.napkin import Idea, napkin

Action = Literal["BUY", "HOLD", "SELL"]


@dataclass
class Signal:
    """One decision, in the documented output format.

    `reason` is not decoration — it names WHICH RULE FIRED. Without it a signal cannot be
    debugged after the fact, and a strategy you cannot debug is one you cannot honestly
    reject either.
    """

    action: Action
    confidence: float          # 0-1. See the warning in `Strategy.signal`.
    reason: str
    price: float
    timestamp: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _Describable(ABC):
    """Anything that must pass the napkin test before it is allowed to run."""

    name: str = "unnamed"

    @abstractmethod
    def describe(self) -> Idea:
        """WHO pays me, WHY, and WHAT BARRIER keeps this from being arbed away.

        Abstract on purpose. Every idea we rejected could have been killed here, before
        implementation, if we had been forced to fill this in first.
        """

    def gate(self) -> dict:
        """Run the napkin test on this strategy's own self-description."""
        return napkin(self.describe())

    def assert_gate(self) -> None:
        """Raise unless the napkin test passes. Call before any live use."""
        r = self.gate()
        if r["verdict"] == "KILL":
            raise ValueError(f"{self.name} fails the napkin test:\n  "
                             + "\n  ".join(r["kills"]))


class Strategy(_Describable):
    """Bar-by-bar strategy. Signals for bar T may use data up to and including T only."""

    @abstractmethod
    def signal(self, df: pd.DataFrame) -> Signal:
        """Decide from an OHLCV frame whose LAST ROW is the current bar.

        NO LOOK-AHEAD: implementations must not index beyond the last row. The caller is
        responsible for slicing — `discipline/firewall.py` enforces this in backtests.

        ON `confidence`: it is the strategy's own opinion of itself and is NOT a
        probability of being right. Ours reported prob_up up to 0.71 while the measured
        forward hit rate was 49.9%. Treat it as an ordering, never as a number.
        """

    def weights(self, df: pd.DataFrame, warmup: int = 60) -> pd.Series:
        """Walk the frame bar by bar -> target exposure in [-1, 1] per bar.

        This is what the backtester and gauntlet consume. Default implementation calls
        `signal()` on expanding slices, so a strategy only has to implement one method.
        Slow but correct; override for a vectorised version if it matters.
        """
        out = pd.Series(0.0, index=df.index, dtype=float)
        mapping = {"BUY": 1.0, "SELL": -1.0, "HOLD": 0.0}
        for i in range(warmup, len(df)):
            s = self.signal(df.iloc[: i + 1])       # <= T only
            out.iloc[i] = mapping[s.action] * max(0.0, min(1.0, s.confidence))
        return out


class MechanismStudy(_Describable):
    """Event-driven study. Produces a measured edge, not a per-bar signal.

    This is the shape our surviving work actually takes: `escalation` finds episodes and
    sums realised funding; `liq_dislocation` measures fills against mark. Forcing these
    into a bar-by-bar `signal()` would be a lie about what they do.
    """

    @abstractmethod
    def measure(self) -> dict:
        """Return at least {'edge_bps', 'n', 'capacity_usd'} from real observations.

        The result should be the CHEAPEST decisive measurement, not a backtest. Three of
        our five rejections were settled this way in hours: liq_meanrev needed no
        backtest because the mark price rides on every Kraken execution.
        """
