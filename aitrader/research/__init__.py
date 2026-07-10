"""Edge Research Factory — Stage 1: Hypothesis Registry + multiple-testing correction.

Rule: NO backtest without a logged economic rationale ("who pays me and why").
Every idea — pass or fail — is recorded, so we can count total trials and DEFLATE
the Sharpe. Without this, a Sharpe of 1+ from 50 tries is almost surely luck.
"""
from .registry import HypothesisRegistry, Hypothesis
from .deflated_sharpe import expected_max_sharpe, deflated_sharpe_ratio

__all__ = ["HypothesisRegistry", "Hypothesis",
           "expected_max_sharpe", "deflated_sharpe_ratio"]
