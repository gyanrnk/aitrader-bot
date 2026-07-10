"""Typed decision objects. Every agent emits one of these — never raw text.

This is TradingAgents' "structured output" discipline: force each stage into a
schema so the next stage (and the deterministic rating parser) never has to guess.
Using stdlib dataclasses keeps the core dependency-free; swap for pydantic if you
want validation on live LLM output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Rating(str, Enum):
    """5-tier portfolio rating (TradingAgents-style)."""
    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"


@dataclass
class AnalystReport:
    analyst: str                 # market | news | sentiment | fundamentals
    stance: float                # -1.0 (bearish) .. +1.0 (bullish)
    confidence: float            # 0.0 .. 1.0
    summary: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class DebateTurn:
    speaker: str                 # "Bull" | "Bear" | "Aggressive" | ...
    argument: str
    round: int


@dataclass
class TraderProposal:
    action: Action
    conviction: float            # 0.0 .. 1.0
    thesis: str
    stop_loss_pct: float = 0.05  # for volatility/risk sizing
    horizon_days: int = 5


@dataclass
class RiskDecision:
    approved: bool
    rating: Rating
    rationale: str
    adjustments: str = ""        # e.g. "halve size; tighten stop"


@dataclass
class FinalDecision:
    symbol: str
    as_of: str
    action: Action
    rating: Rating
    target_weight: float         # fraction of equity, signed (+long / -short)
    conviction: float
    reason: str
    approved: bool
