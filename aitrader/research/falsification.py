"""Falsification audit (Nikolopoulos 2026) — the leakage/self-deception detector.

Run the SAME strategy on many SHUFFLED copies of the driver series (time structure
destroyed). Build a null distribution of Sharpes. Then:

  p_value = fraction of null (shuffled) Sharpes >= the real Sharpe.

If p is high, the real result is NOT distinguishable from luck on structureless data —
i.e. the strategy's "edge" is timing-luck or leakage, not real skill. Also reveals when
a carry-type return is just harvesting a positive AVERAGE (null stays high) rather than
adding timing value. Pure computation — free.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def falsification_audit(driver: pd.Series, strategy_fn, real_sharpe: float,
                        n_shuffles: int = 200, seed: int = 7) -> dict:
    """driver: the series the strategy keys off (e.g. funding).
    strategy_fn(shuffled_series) -> per-period net return Series.
    real_sharpe: the strategy's Sharpe on the REAL (unshuffled) driver.
    """
    rng = np.random.default_rng(seed)
    vals = driver.to_numpy()
    null = []
    for _ in range(n_shuffles):
        shuffled = pd.Series(rng.permutation(vals), index=driver.index)
        r = strategy_fn(shuffled)
        r = r.to_numpy()
        r = r[np.isfinite(r)]
        sd = r.std(ddof=1) if r.size > 1 else 0.0
        null.append(r.mean() / sd if sd > 0 else 0.0)
    null = np.array(null)
    # scale null Sharpes to same annualization as real (per-period -> caller passes annualized real)
    p_value = float((null >= _to_per_period(real_sharpe)).mean())
    return {
        "null_mean_sharpe": round(float(null.mean()), 3),
        "null_p95_sharpe": round(float(np.percentile(null, 95)), 3),
        "p_value": round(p_value, 3),
        "falsified": bool(p_value > 0.05),   # real not clearly above null -> suspect
    }


def _to_per_period(annualized_sharpe: float, periods_per_year: int = 3 * 365) -> float:
    return annualized_sharpe / np.sqrt(periods_per_year)
