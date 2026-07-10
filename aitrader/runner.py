"""High-level orchestrator tying the layers together for a single live cycle.

    data -> features -> decision graph -> broker (paper) -> (later) reflection

This is what a scheduler (cron / Celery beat) would call once per symbol per bar.
"""
from __future__ import annotations

from .config import Settings, load_settings
from .data import get_provider
from .data.indicators import compute_features
from .discipline.firewall import assert_point_in_time
from .execution import get_broker
from .execution.broker import Order
from .memory import LayeredMemory
from .orchestration import DecisionGraph
from .schemas import FinalDecision
from .state import TradingState


class TradingBot:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.provider = get_provider(self.settings)
        self.broker = get_broker(self.settings)
        self.memory = LayeredMemory(
            recency_factor=self.settings.memory_recency_factor,
            importance_decay=self.settings.memory_importance_decay,
        )
        self.graph = DecisionGraph(self.settings, memory=self.memory)

    def decide(self, symbol: str) -> tuple[FinalDecision, TradingState]:
        ohlcv = self.provider.ohlcv(symbol)
        as_of = ohlcv.index[-1]
        ohlcv = assert_point_in_time(ohlcv, as_of)     # firewall guard
        state = TradingState(
            symbol=symbol, as_of=str(as_of), ohlcv=ohlcv,
            features=compute_features(ohlcv),
        )
        self.memory.step_decay()
        decision = self.graph.run(state)
        return decision, state

    def execute(self, decision: FinalDecision, price: float) -> object:
        order = Order(decision.symbol, decision.action, decision.target_weight)
        return self.broker.target(order, price, self.settings.starting_equity)
