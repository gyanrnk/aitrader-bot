"""Bounded-debate routing (TradingAgents `conditional_logic.py`).

The debate alternates speakers for a fixed number of rounds, THEN hands to the
manager. This cap is what keeps an adversarial LLM debate from running forever
while still forcing every thesis to survive a counter-argument.
"""
from __future__ import annotations

from ..state import TradingState


class ConditionalLogic:
    def __init__(self, max_debate_rounds: int = 1, max_risk_rounds: int = 1):
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_rounds = max_risk_rounds

    def next_investment_speaker(self, state: TradingState) -> str:
        """Return 'Bull' | 'Bear' | 'ResearchManager'."""
        if state.debate_count >= 2 * self.max_debate_rounds:
            return "ResearchManager"
        # alternate; bull opens
        return "Bear" if state.last_debater == "Bull" else "Bull"

    def next_risk_speaker(self, state: TradingState) -> str:
        """Return one of Aggressive | Conservative | Neutral | PortfolioManager."""
        if state.risk_count >= 3 * self.max_risk_rounds:
            return "PortfolioManager"
        order = {"": "Aggressive", "Aggressive": "Conservative",
                 "Conservative": "Neutral", "Neutral": "Aggressive"}
        return order[state.last_risk_speaker]
