"""TradingState: the single mutable object passed between every node in the graph.

Direct analogue of TradingAgents' `AgentState` TypedDict — but a dataclass so the
IDE/type-checker helps you. Nodes read what they need and write their output back.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any

import pandas as pd

from .schemas import (
    AnalystReport,
    DebateTurn,
    TraderProposal,
    RiskDecision,
    FinalDecision,
)


@dataclass
class TradingState:
    # inputs
    symbol: str
    as_of: str                                   # decision timestamp (ISO)
    ohlcv: pd.DataFrame                           # point-in-time market history
    features: dict[str, float] = field(default_factory=dict)   # indicators at as_of
    context: dict[str, Any] = field(default_factory=dict)      # news/sentiment blobs

    # memory recalled for this decision
    memories: list[str] = field(default_factory=list)

    # stage outputs
    reports: list[AnalystReport] = field(default_factory=list)
    investment_debate: list[DebateTurn] = field(default_factory=list)
    investment_plan: str = ""
    proposal: Optional[TraderProposal] = None
    risk_debate: list[DebateTurn] = field(default_factory=list)
    risk_decision: Optional[RiskDecision] = None
    decision: Optional[FinalDecision] = None

    # debate bookkeeping (drives conditional_logic routing)
    debate_count: int = 0
    last_debater: str = ""
    risk_count: int = 0
    last_risk_speaker: str = ""

    def net_stance(self) -> float:
        """Confidence-weighted average analyst stance in [-1, 1]."""
        if not self.reports:
            return 0.0
        num = sum(r.stance * r.confidence for r in self.reports)
        den = sum(r.confidence for r in self.reports) or 1.0
        return num / den
