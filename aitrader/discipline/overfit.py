"""Overfit / reward-hacking detection (agent-backtest-lab `leakage/reward_hacking.py`).

Asks: does THIS strategy do much better on the window it was tuned on than on
holdout? Signals:
  A. In-sample Sharpe good but out-of-sample Sharpe collapses.
  B. Out-of-sample max-drawdown materially worse than in-sample.
These are heuristics rendered as warn/critical flags, not statistical guarantees.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def sharpe(returns: pd.Series, ann: int = 252) -> float:
    r = returns.dropna().to_numpy()
    if r.size < 2:
        return float("nan")
    sd = r.std(ddof=1)
    if sd <= 0:
        return float("nan")
    return float(r.mean() / sd * np.sqrt(ann))


def max_drawdown(returns: pd.Series) -> float:
    equity = (1 + returns.fillna(0)).cumprod()
    peak = equity.cummax()
    return float(((equity - peak) / peak).min())


@dataclass
class Flag:
    code: str
    severity: str        # info | warn | critical
    message: str


def detect_reward_hacking(returns: pd.Series, is_fraction: float = 0.7) -> list[Flag]:
    flags: list[Flag] = []
    r = returns.dropna()
    if len(r) < 20:
        return [Flag("insufficient_data", "info", "Too few points to judge overfit.")]
    split = int(len(r) * is_fraction)
    is_r, oos_r = r.iloc[:split], r.iloc[split:]

    is_s, oos_s = sharpe(is_r), sharpe(oos_r)
    if np.isfinite(is_s) and np.isfinite(oos_s) and is_s > 0.5 and oos_s < is_s * 0.5:
        flags.append(Flag("sharpe_drop", "critical",
                          f"Sharpe collapses IS={is_s:.2f} -> OOS={oos_s:.2f}."))

    is_dd, oos_dd = max_drawdown(is_r), max_drawdown(oos_r)
    if oos_dd < is_dd * 1.5 and oos_dd < -0.05:
        flags.append(Flag("drawdown_shift", "warn",
                          f"Drawdown worsens IS={is_dd:.1%} -> OOS={oos_dd:.1%}."))
    if not flags:
        flags.append(Flag("ok", "info", "No IS/OOS overfit signal detected."))
    return flags


def scorecard(strategy: pd.Series, baselines: dict[str, pd.Series]) -> dict:
    """Compact, net-of-cost verdict: Sharpe, drawdown, baseline comparison, flags."""
    strat_sharpe = sharpe(strategy)
    bh_sharpe = sharpe(baselines.get("buy_and_hold", strategy))
    beat = {k: sharpe(strategy) > sharpe(v) for k, v in baselines.items()}
    return {
        "sharpe": round(strat_sharpe, 3),
        "max_drawdown": round(max_drawdown(strategy), 4),
        "total_return": round(float((1 + strategy.fillna(0)).prod() - 1), 4),
        "beats_buy_and_hold": strat_sharpe > bh_sharpe,
        "beats_baselines": beat,
        "overfit_flags": [f.__dict__ for f in detect_reward_hacking(strategy)],
    }
