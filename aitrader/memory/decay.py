"""Exponential decay — memories fade unless reinforced (FinMem `decay.py`).

    recency    = exp(-delta / recency_factor)   # newer -> closer to 1
    importance = importance * importance_decay   # erodes each step

A loss pattern from months ago should not dominate today's decision. Decay is what
makes that automatic instead of a manual cleanup job.
"""
from __future__ import annotations

import math


def exponential_decay(
    importance: float,
    delta: float,
    recency_factor: float = 10.0,
    importance_decay: float = 0.988,
) -> tuple[float, float, float]:
    """Return (new_recency, new_importance, new_delta) after one step of aging."""
    delta += 1
    new_recency = math.exp(-(delta / recency_factor))
    new_importance = importance * importance_decay
    return new_recency, new_importance, delta
