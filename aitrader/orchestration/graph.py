"""DecisionGraph: run one symbol through the full agent pipeline.

Flow (TradingAgents topology):
    analysts -> [Bull<->Bear debate] -> research manager -> trader
             -> [Aggressive/Conservative/Neutral risk debate] -> portfolio manager
             -> risk sizing -> FinalDecision

Deterministic in mock mode; identical structure in live mode with real LLM calls.
"""
from __future__ import annotations

from ..config import Settings
from ..schemas import Action, FinalDecision
from ..state import TradingState
from ..agents import roles
from ..agents.llm import build_llm, QuantEngine
from ..risk.position_sizing import size_position
from .conditional_logic import ConditionalLogic


class DecisionGraph:
    def __init__(self, settings: Settings, memory=None):
        self.settings = settings
        # slow_llm = the configured backend (groq/claude/quant) for regime/news/reflection.
        self.slow_llm = build_llm(settings)
        # Per-bar hot path stays FREE (QuantEngine) unless you explicitly opt in.
        self.llm = self.slow_llm if settings.use_llm_in_decision else QuantEngine()
        self.memory = memory
        self.logic = ConditionalLogic(settings.max_debate_rounds, settings.max_risk_rounds)

    def run(self, state: TradingState) -> FinalDecision:
        s = self.settings

        # 0. recall relevant memory for this decision
        if self.memory is not None:
            q = f"{state.symbol} trend {state.features.get('trend', 0):+.2f} rsi {state.features.get('rsi14', 50):.0f}"
            state.memories = [m.text for m in self.memory.retrieve(q, s.memory_top_k)]

        # 1. analysts
        for role in s.analysts:
            roles.run_analyst(state, role, self.llm)

        # 2. bull vs bear debate (bounded)
        while True:
            nxt = self.logic.next_investment_speaker(state)
            if nxt == "ResearchManager":
                roles.run_research_manager(state, self.llm)
                break
            (roles.run_bull if nxt == "Bull" else roles.run_bear)(state, self.llm)

        # 3. trader proposal
        roles.run_trader(state, self.llm)

        # 4. risk debate (3-way, bounded) + portfolio manager
        while True:
            nxt = self.logic.next_risk_speaker(state)
            if nxt == "PortfolioManager":
                roles.run_portfolio_manager(state, self.llm)
                break
            roles.run_risk_debator(state, nxt, self.llm)

        # 5. position sizing -> final decision
        rd = state.risk_decision
        proposal = state.proposal
        weight = 0.0
        if rd.approved and proposal.action != Action.HOLD:
            weight = size_position(
                conviction=proposal.conviction,
                stop_loss_pct=proposal.stop_loss_pct,
                settings=s,
            )
            if proposal.action == Action.SELL:
                weight = -weight
            if rd.adjustments.startswith("reduce"):
                weight *= 0.5

        decision = FinalDecision(
            symbol=state.symbol,
            as_of=state.as_of,
            action=proposal.action if rd.approved else Action.HOLD,
            rating=rd.rating,
            target_weight=round(weight, 4),
            conviction=proposal.conviction,
            reason=f"{rd.rationale}. {rd.adjustments}".strip(". "),
            approved=rd.approved,
        )
        state.decision = decision
        return decision
