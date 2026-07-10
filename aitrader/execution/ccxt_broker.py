"""Live crypto execution via ccxt (SKELETON — review before enabling real orders).

Deliberately minimal and guarded. Real trading needs idempotency keys, order-status
reconciliation, partial-fill handling, and rate-limit backoff before you trust it.
"""
from __future__ import annotations

import os

from ..config import Settings
from ..schemas import Action
from .broker import Order, Fill


class CcxtBroker:
    def __init__(self, settings: Settings):
        import ccxt  # local import
        ex_name = os.getenv("CCXT_EXCHANGE", "binance")
        self.settings = settings
        self.exchange = getattr(ccxt, ex_name)({
            "apiKey": os.getenv("CCXT_API_KEY", ""),
            "secret": os.getenv("CCXT_SECRET", ""),
            "enableRateLimit": True,
        })
        self._positions: dict[str, float] = {}

    def target(self, order: Order, price: float, equity: float) -> Fill:
        # SAFETY: refuse to place real orders unless explicitly unlocked.
        if os.getenv("AITRADER_ALLOW_LIVE_ORDERS") != "yes":
            raise RuntimeError(
                "Live orders disabled. Set AITRADER_ALLOW_LIVE_ORDERS=yes to enable, "
                "and only after reviewing idempotency/reconciliation handling."
            )
        prev = self._positions.get(order.symbol, 0.0)
        delta_w = order.target_weight - prev
        notional = abs(delta_w) * equity
        amount = notional / price
        side = "buy" if delta_w > 0 else "sell"
        # self.exchange.create_order(order.symbol, "market", side, amount)  # <- real call
        cost = abs(delta_w) * (self.settings.cost_bps_per_side / 1e4)
        self._positions[order.symbol] = order.target_weight
        return Fill(order.symbol, order.action, price, order.target_weight, cost)

    def positions(self) -> dict[str, float]:
        return dict(self._positions)
