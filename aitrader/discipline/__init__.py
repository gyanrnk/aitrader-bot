"""Discipline layer — the gate that separates a real system from a demo.

Everything here exists to stop you deceiving yourself: costs, lookahead leakage,
must-beat baselines, and in-sample/out-of-sample overfit detection.
Adapted from agent-backtest-lab (abl).
"""
from .costs import ConstantBpsCost, net_returns
from .baselines import buy_and_hold, run_baselines
from .firewall import assert_point_in_time
from .overfit import sharpe, detect_reward_hacking, scorecard

__all__ = [
    "ConstantBpsCost", "net_returns", "buy_and_hold", "run_baselines",
    "assert_point_in_time", "sharpe", "detect_reward_hacking", "scorecard",
]
