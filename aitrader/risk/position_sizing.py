"""Position sizing: risk-per-trade with hard caps.

target_weight = risk_per_trade / stop_loss   (fixed-fractional / "risk unit")
scaled by conviction, then clamped to max_position_pct and gross exposure.

This is deliberately conservative: the cap matters more than the model. Most
blow-ups are a sizing failure, not a signal failure.
"""
from __future__ import annotations

from ..config import Settings


def size_position(conviction: float, stop_loss_pct: float, settings: Settings) -> float:
    """Return an unsigned target weight (fraction of equity) in [0, max_position_pct]."""
    stop = max(stop_loss_pct, 0.005)
    # risk_per_trade of equity, translated to a position weight via the stop distance
    risk_unit = settings.risk_per_trade_pct / stop
    weight = risk_unit * max(0.0, min(1.0, conviction))
    weight = min(weight, settings.max_position_pct)
    weight = min(weight, settings.max_gross_exposure)
    return round(weight, 4)
