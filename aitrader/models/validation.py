"""Purged + embargoed walk-forward splits.

Ordinary K-fold CV leaks the future into the past and produces beautiful, fake
accuracy. For time series with overlapping labels you MUST:
  * only ever test on data AFTER the training window (walk-forward), and
  * purge/embargo a gap between train and test so a label's horizon can't overlap
    the test set (López de Prado).
This is the validation half of "don't fool yourself".
"""
from __future__ import annotations

from typing import Iterator

import numpy as np


def purged_walk_forward_splits(
    n: int,
    n_splits: int = 5,
    embargo: int = 5,
    min_train: int = 100,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield (train_idx, test_idx) expanding-window splits with an embargo gap."""
    fold = (n - min_train) // n_splits
    if fold <= 0:
        return
    for k in range(n_splits):
        train_end = min_train + k * fold
        test_start = train_end + embargo
        test_end = test_start + fold
        if test_start >= n:
            break
        train_idx = np.arange(0, train_end)
        test_idx = np.arange(test_start, min(test_end, n))
        if len(test_idx) == 0:
            break
        yield train_idx, test_idx
