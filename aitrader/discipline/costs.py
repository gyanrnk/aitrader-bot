"""Transaction costs. THE RULE: every P&L reported to a human is NET of costs.

`bps_each_side` is charged on each side; a round-trip costs 2x. 5 bps/side is a
conservative-but-realistic retail default (agent-backtest-lab `costs/models.py`).
"""
from __future__ import annotations

import pandas as pd


class ConstantBpsCost:
    def __init__(self, bps_each_side: float = 5.0):
        self.bps_each_side = bps_each_side
        self.name = "constant_bps"

    def cost_fraction(self, turnover: pd.Series) -> pd.Series:
        """Per-period cost as a fraction of equity from |change in exposure|."""
        return turnover.abs() * (self.bps_each_side / 1e4)


def net_returns(
    gross: pd.Series, weights: pd.Series, bps_each_side: float = 5.0
) -> pd.Series:
    """Convert gross strategy returns to NET returns after turnover costs.

    gross   : per-period strategy return BEFORE costs (weight_{t-1} * asset_ret_t)
    weights : per-period target weight series (to compute turnover)
    """
    turnover = weights.diff().abs().fillna(weights.abs())
    cost = ConstantBpsCost(bps_each_side).cost_fraction(turnover)
    return gross - cost
