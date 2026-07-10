"""Probability of Backtest Overfitting (PBO) via CSCV — Bailey & López de Prado.

Idea: given many strategy configs, split time into S blocks, try every way to pick
half as in-sample. In each split, take the config that looked BEST in-sample and see
where it ranks out-of-sample. If the in-sample winner is usually below the OOS median,
your selection process is overfitting.

  PBO = fraction of splits where the IS-best strategy has OOS rank below median.
PBO > 0.5 means picking the in-sample winner is worse than useless. Free to compute.
"""
from __future__ import annotations

import math
from itertools import combinations

import numpy as np


def _metric(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    s = x.std(ddof=1) if x.size > 1 else 0.0
    return float(x.mean() / s) if s > 0 else 0.0


def cscv_pbo(perf: np.ndarray, n_blocks: int = 8) -> dict:
    """perf: (T observations x N strategies) per-period return matrix."""
    T, N = perf.shape
    if N < 2:
        return {"pbo": None, "note": "need >=2 configs for PBO"}
    S = n_blocks - (n_blocks % 2)
    rows = np.array_split(np.arange(T - T % S), S)
    logits = []
    for combo in combinations(range(S), S // 2):
        is_idx = np.concatenate([rows[i] for i in combo])
        oos_idx = np.concatenate([rows[i] for i in range(S) if i not in combo])
        is_perf = np.array([_metric(perf[is_idx, n]) for n in range(N)])
        oos_perf = np.array([_metric(perf[oos_idx, n]) for n in range(N)])
        n_star = int(np.argmax(is_perf))
        rank = int((oos_perf <= oos_perf[n_star]).sum())      # 1..N, higher = better
        w = rank / (N + 1)
        w = min(max(w, 1e-6), 1 - 1e-6)
        logits.append(math.log(w / (1 - w)))
    logits = np.array(logits)
    return {
        "pbo": round(float((logits <= 0).mean()), 3),   # P(IS-winner below OOS median)
        "n_configs": N,
        "n_splits": len(logits),
        "passes": bool((logits <= 0).mean() < 0.5),
    }
