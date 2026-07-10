"""Paper broker: simulates fills and charges realistic costs. Safe default.

Never moves real money. Applies the same net-of-cost model used in backtests, so
paper P&L and backtest P&L are consistent.
"""
from __future__ import annotations

from ..config import Settings
from ..schemas import Action
from .broker import Order, Fill


class PaperBroker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._positions: dict[str, float] = {}   # symbol -> current weight

    def target(self, order: Order, price: float, equity: float) -> Fill:
        prev = self._positions.get(order.symbol, 0.0)
        new_w = order.target_weight
        turnover = abs(new_w - prev)                      # weight traded
        cost = turnover * (self.settings.cost_bps_per_side / 1e4)
        self._positions[order.symbol] = new_w
        return Fill(order.symbol, order.action, price, new_w, cost)

    def positions(self) -> dict[str, float]:
        return dict(self._positions)
