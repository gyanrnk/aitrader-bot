"""ML prediction layer: engineered features -> triple-barrier labels ->
gradient-boosted classifier -> calibrated probability, validated with purged
walk-forward CV. The probability feeds the decision graph as one more analyst.

Honest framing (see ECONOMICS.md): the goal is a *calibrated edge* validated
out-of-sample and net of cost — NOT a high in-sample accuracy number.
"""
from .features import build_features
from .labeling import triple_barrier_labels
from .predictor import Predictor
from .validation import purged_walk_forward_splits

__all__ = ["build_features", "triple_barrier_labels", "Predictor",
           "purged_walk_forward_splits"]
