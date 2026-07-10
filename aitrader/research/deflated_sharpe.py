"""Deflated Sharpe Ratio (López de Prado) — correct for multiple testing.

If you try N strategies, the best one's Sharpe is inflated just by luck. Two tools:

  expected_max_sharpe(N) : the Sharpe you'd expect the BEST of N random (zero-edge)
                           strategies to show. Your observed Sharpe must clear THIS,
                           not zero.
  deflated_sharpe_ratio  : probability the observed Sharpe is real given N trials and
                           the sample's length/skew/kurtosis. > 0.95 = trustworthy.

No scipy needed — uses statistics.NormalDist (stdlib) for the normal CDF/quantile.
"""
from __future__ import annotations

import math
from statistics import NormalDist

_N = NormalDist()
_EULER = 0.5772156649015329  # Euler–Mascheroni constant


def expected_max_sharpe(n_trials: int, sharpe_std: float = 1.0) -> float:
    """Expected maximum Sharpe of `n_trials` independent zero-edge strategies.

    sharpe_std = cross-trial dispersion of Sharpe estimates (1.0 is a common default).
    """
    n = max(int(n_trials), 1)
    if n == 1:
        return 0.0
    z1 = _N.inv_cdf(1 - 1.0 / n)
    z2 = _N.inv_cdf(1 - 1.0 / (n * math.e))
    return sharpe_std * ((1 - _EULER) * z1 + _EULER * z2)


def deflated_sharpe_ratio(
    observed_sharpe: float,
    n_trials: int,
    n_obs: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    sharpe_std: float = 1.0,
) -> dict:
    """Return {'benchmark_sharpe', 'dsr', 'passes'} for the observed Sharpe.

    observed_sharpe : per-period Sharpe of the strategy's return series
    n_trials        : how many strategies/variants were tried to find this one
    n_obs           : number of return observations in the backtest
    skew, kurtosis  : of the return series (default normal: 0, 3)
    """
    sr0 = expected_max_sharpe(n_trials, sharpe_std)
    if n_obs < 3:
        return {"benchmark_sharpe": round(sr0, 3), "dsr": 0.0, "passes": False}
    denom = math.sqrt(max(1e-9,
                          1 - skew * observed_sharpe + (kurtosis - 1) / 4.0 * observed_sharpe ** 2))
    z = (observed_sharpe - sr0) * math.sqrt(n_obs - 1) / denom
    dsr = _N.cdf(z)
    return {
        "benchmark_sharpe": round(sr0, 3),   # you must beat THIS, not 0
        "dsr": round(dsr, 4),                 # P(edge is real)
        "passes": dsr >= 0.95,                # standard bar
    }
