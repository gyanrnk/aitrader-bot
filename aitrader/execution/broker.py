"""Broker interface + factory. A ccxt adapter is sketched for live crypto.

Design rule: the graph produces a *target weight*; the broker turns weight deltas
into orders. Swapping paper <-> ccxt never touches decision logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..config import Settings
from ..schemas import Action


@dataclass
class Order:
    symbol: str
    action: Action
    target_weight: float


@dataclass
class Fill:
    symbol: str
    action: Action
    price: float
    weight: float
    cost: float          # transaction cost paid (fraction of equity)


class Broker(Protocol):
    def target(self, order: Order, price: float, equity: float) -> Fill: ...
    def positions(self) -> dict[str, float]: ...


def get_broker(settings: Settings) -> Broker:
    name = settings.broker.lower()
    if name == "ccxt":
        from .ccxt_broker import CcxtBroker
        return CcxtBroker(settings)
    if name == "mt5":
        from .mt5_broker import MT5Broker
        return MT5Broker(settings)
    from .paper_broker import PaperBroker
    return PaperBroker(settings)
