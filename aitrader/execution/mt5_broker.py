"""Forex/CFD execution via MetaTrader 5 (SKELETON — LOCAL Windows only).

Double-gated for safety like the ccxt broker: refuses real orders unless
AITRADER_ALLOW_LIVE_ORDERS=yes. Use a DEMO account first. Lazy-imports MetaTrader5.
"""
from __future__ import annotations

import os

from ..config import Settings
from ..schemas import Action
from .broker import Order, Fill


class MT5Broker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._positions: dict[str, float] = {}

    def _mt5(self):
        try:
            import MetaTrader5 as mt5
        except Exception as e:
            raise RuntimeError("MetaTrader5 package missing (pip install MetaTrader5, Windows).") from e
        s = self.settings
        ok = mt5.initialize(login=s.mt5_login, password=s.mt5_password, server=s.mt5_server) \
            if s.mt5_login else mt5.initialize()
        if not ok:
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        return mt5

    def target(self, order: Order, price: float, equity: float) -> Fill:
        if os.getenv("AITRADER_ALLOW_LIVE_ORDERS") != "yes":
            raise RuntimeError(
                "Live orders disabled. Use a DEMO account and set AITRADER_ALLOW_LIVE_ORDERS=yes "
                "only after reviewing lot-sizing, slippage and swap handling.")
        mt5 = self._mt5()
        prev = self._positions.get(order.symbol, 0.0)
        delta_w = order.target_weight - prev
        # NOTE: real lot sizing from equity/contract-size/leverage goes here.
        # request = {"action": mt5.TRADE_ACTION_DEAL, "symbol": order.symbol,
        #            "volume": lots, "type": mt5.ORDER_TYPE_BUY if delta_w>0 else mt5.ORDER_TYPE_SELL,
        #            "price": price, "deviation": 20, "type_filling": mt5.ORDER_FILLING_IOC}
        # result = mt5.order_send(request)   # <- real order
        cost = abs(delta_w) * (self.settings.cost_bps_per_side / 1e4)
        mt5.shutdown()
        self._positions[order.symbol] = order.target_weight
        return Fill(order.symbol, order.action, price, order.target_weight, cost)

    def positions(self) -> dict[str, float]:
        return dict(self._positions)
