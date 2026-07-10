"""Stage 4 — the Validation Gauntlet. The stage that kills 90% of survivors (its job).

Runs every free anti-self-deception check on a candidate and returns ONE honest
verdict. Wired for the funding-carry candidate but the checks are reusable.

Checks (all free / pure compute):
  1. Param plateau  — does performance degrade gently across a param grid, or is the
     winner an isolated spike (curve-fit)?
  2. PBO (CSCV)     — is picking the in-sample winner better than a coin flip?
  3. Cost stress    — does the edge survive 2x and 3x transaction costs?
  4. Multi-asset    — is it positive on most assets, not one lucky one?
  5. Deflated Sharpe— does it beat the multiple-testing luck benchmark?
  6. Falsification  — is it distinguishable from the same strategy on shuffled data?
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .deflated_sharpe import deflated_sharpe_ratio
from .falsification import falsification_audit
from .funding_backtest import carry_net_returns, ENTRY_THRESH, ONE_WAY_COST
from .funding_data import fetch_funding, PERIODS_PER_YEAR
from .pbo import cscv_pbo


def _sharpe(r: pd.Series, ppy: int = PERIODS_PER_YEAR) -> float:
    r = r.dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * np.sqrt(ppy))


def _plateau_check(config_sharpe: dict, best) -> dict:
    """Generic: >=60% of grid configs positive AND best not an isolated spike."""
    sh = np.array([v for v in config_sharpe.values() if np.isfinite(v)])
    pos = sh[sh > 0]
    positive_frac = float((sh > 0).mean())
    med_pos = float(np.median(pos)) if pos.size else float("nan")
    spike = float(config_sharpe[best] / med_pos) if med_pos == med_pos and med_pos else float("inf")
    return {
        "grid_sharpes": {str(g): round(v, 2) for g, v in config_sharpe.items()},
        "best_sharpe": round(config_sharpe[best], 2),
        "positive_frac": round(positive_frac, 2),
        "spike_vs_pos_median": round(spike, 2),
        "passes": bool(positive_frac >= 0.6 and spike < 3.0),
    }


def _pbo_check(config_series: dict, grid) -> dict:
    M = pd.concat([config_series[g] for g in grid], axis=1).dropna().to_numpy()
    return cscv_pbo(M, n_blocks=8)


def _verdict(passed: dict) -> dict:
    return {
        "checks_passed": f"{sum(bool(v) for v in passed.values())}/{len(passed)}",
        "detail": passed,
        "deployable": all(bool(v) for v in passed.values()),
    }


def run_gauntlet(symbols: list[str], years: float = 2.0) -> dict:
    funding = {s: fetch_funding(s, years=years)["funding"] for s in symbols}

    # ---- param grid (small, pre-declared) ----
    entries = [0.00005, 0.0001, 0.0002]
    exits = [0.0, 0.00005]
    grid = [(e, x) for e in entries for x in exits]

    # per-config pooled net return series (mean across assets)
    def pooled(entry, exit, cost=ONE_WAY_COST):
        cols = [carry_net_returns(funding[s], entry=entry, exit=exit, one_way_cost=cost)
                for s in symbols]
        return pd.concat(cols, axis=1).mean(axis=1)

    config_series = {g: pooled(*g) for g in grid}
    config_sharpe = {g: _sharpe(s) for g, s in config_series.items()}
    best = max(config_sharpe, key=lambda g: config_sharpe[g])
    best_series = config_series[best]

    # 1. param plateau: MOST configs should be positive AND best not an isolated spike.
    #    A negative-median grid = param-sensitive (half the settings lose) -> FAIL.
    sh = np.array([v for v in config_sharpe.values() if np.isfinite(v)])
    pos = sh[sh > 0]
    positive_frac = float((sh > 0).mean())
    med_pos = float(np.median(pos)) if pos.size else float("nan")
    spike = float(config_sharpe[best] / med_pos) if med_pos and med_pos == med_pos else float("inf")
    plateau = {
        "grid_sharpes": {str(g): round(v, 2) for g, v in config_sharpe.items()},
        "best_config": {"entry": best[0], "exit": best[1], "sharpe": round(config_sharpe[best], 2)},
        "positive_frac": round(positive_frac, 2),
        "spike_vs_pos_median": round(spike, 2),
        # honest gate: >=60% of configs positive AND best within 3x the positive median
        "passes": bool(positive_frac >= 0.6 and spike < 3.0),
    }

    # 2. PBO on the config x time matrix
    M = pd.concat([config_series[g] for g in grid], axis=1).dropna().to_numpy()
    pbo = cscv_pbo(M, n_blocks=8)

    # 3. cost stress at best config
    cost_stress = {
        f"{mult}x": round(_sharpe(pooled(best[0], best[1], cost=ONE_WAY_COST * mult)), 2)
        for mult in (1, 2, 3)
    }
    cost_stress["passes"] = bool(cost_stress["3x"] > 0)

    # 4. multi-asset consistency at best config
    per_asset = {s: _sharpe(carry_net_returns(funding[s], entry=best[0], exit=best[1]))
                 for s in symbols}
    pct_pos = float(np.mean([v > 0 for v in per_asset.values()]))
    multi_asset = {"per_asset_sharpe": {k: round(v, 2) for k, v in per_asset.items()},
                   "pct_positive": pct_pos, "passes": bool(pct_pos >= 0.75)}

    # 5. deflated Sharpe (n_trials = grid size)
    dsr = deflated_sharpe_ratio(config_sharpe[best], n_trials=len(grid),
                                n_obs=int(best_series.notna().sum()))

    # 6. falsification: shuffle funding, re-run best config
    def strat_on(shuffled):  # single-asset proxy on pooled driver
        return carry_net_returns(shuffled, entry=best[0], exit=best[1])
    # use the highest-funding asset's series as the driver proxy
    drv = max(funding.values(), key=lambda s: s.mean())
    fals = falsification_audit(drv, strat_on, real_sharpe=config_sharpe[best], n_shuffles=150)

    checks = {
        "param_plateau": plateau,
        "pbo": pbo,
        "cost_stress": cost_stress,
        "multi_asset": multi_asset,
        "deflated_sharpe": dsr,
        "falsification": fals,
    }
    passed = {
        "plateau": plateau["passes"],
        "pbo": pbo.get("passes"),
        "cost_stress": cost_stress["passes"],
        "multi_asset": multi_asset["passes"],
        "dsr": dsr["passes"],
        "not_falsified": not fals["falsified"],
    }
    checks["VERDICT"] = _verdict(passed)
    return checks


def run_carry_core_gauntlet(symbols: list[str], years: float = 2.0) -> dict:
    """Gauntlet on the ROBUST continuous carry (funding-proportional, no threshold cliff)."""
    from .funding_backtest import carry_core_returns
    funding = {s: fetch_funding(s, years=years)["funding"] for s in symbols}

    spans = [2, 3, 5]
    scales = [0.0002, 0.0003, 0.0005]
    grid = [(sp, sc) for sp in spans for sc in scales]

    def pooled(sp, sc, cost=ONE_WAY_COST):
        cols = [carry_core_returns(funding[s], ema_span=sp, scale=sc, one_way_cost=cost)
                for s in symbols]
        return pd.concat(cols, axis=1).mean(axis=1)

    config_series = {g: pooled(*g) for g in grid}
    config_sharpe = {g: _sharpe(s) for g, s in config_series.items()}
    best = max(config_sharpe, key=lambda g: config_sharpe[g])

    plateau = _plateau_check(config_sharpe, best)
    plateau["best_config"] = {"ema_span": best[0], "scale": best[1]}
    pbo = _pbo_check(config_series, grid)
    cost_stress = {f"{m}x": round(_sharpe(pooled(best[0], best[1], cost=ONE_WAY_COST * m)), 2)
                   for m in (1, 2, 3)}
    cost_stress["passes"] = bool(cost_stress["3x"] > 0)
    per_asset = {s: _sharpe(carry_core_returns(funding[s], ema_span=best[0], scale=best[1]))
                 for s in symbols}
    pct_pos = float(np.mean([v > 0 for v in per_asset.values()]))
    multi_asset = {"per_asset_sharpe": {k: round(v, 2) for k, v in per_asset.items()},
                   "pct_positive": pct_pos, "passes": bool(pct_pos >= 0.75)}
    best_series = config_series[best]
    dsr = deflated_sharpe_ratio(config_sharpe[best], n_trials=len(grid),
                                n_obs=int(best_series.notna().sum()))
    drv = max(funding.values(), key=lambda s: s.mean())
    fals = falsification_audit(
        drv, lambda sh: carry_core_returns(sh, ema_span=best[0], scale=best[1]),
        real_sharpe=config_sharpe[best], n_shuffles=150, periods_per_year=PERIODS_PER_YEAR)

    # annualized net return of best config (money view, not just Sharpe)
    apr = float(best_series.mean() * PERIODS_PER_YEAR)
    passed = {
        "plateau": plateau["passes"], "pbo": pbo.get("passes"),
        "cost_stress": cost_stress["passes"], "multi_asset": multi_asset["passes"],
        "dsr": dsr["passes"], "not_falsified": not fals["falsified"],
    }
    return {"param_plateau": plateau, "pbo": pbo, "cost_stress": cost_stress,
            "multi_asset": multi_asset, "deflated_sharpe": dsr, "falsification": fals,
            "net_apr": round(apr, 4), "VERDICT": _verdict(passed)}


def run_tsmom_gauntlet(symbols: list[str]) -> dict:
    """Same gauntlet, applied to the time-series-momentum candidate on daily prices."""
    from .tsmom_backtest import (tsmom_net_returns, tsmom_from_returns,
                                 load_prices, PERIODS_PER_YEAR as PPY, COST_PER_SIDE)

    prices = load_prices(symbols, lookback=900)
    if not prices:
        return {"error": "no price data (yfinance unreachable)"}
    rets = {s: p.pct_change().fillna(0.0) for s, p in prices.items()}

    lookbacks = [7, 14, 30, 60, 90]                    # param grid
    def pooled(lb, cost=COST_PER_SIDE):
        cols = [tsmom_from_returns(rets[s], lookback=lb, cost=cost) for s in prices]
        return pd.concat(cols, axis=1).mean(axis=1)

    config_series = {lb: pooled(lb) for lb in lookbacks}
    config_sharpe = {lb: _sharpe(s, PPY) for lb, s in config_series.items()}
    best = max(config_sharpe, key=lambda k: config_sharpe[k])

    plateau = _plateau_check(config_sharpe, best)
    plateau["best_config"] = {"lookback": best}
    pbo = _pbo_check(config_series, lookbacks)
    cost_stress = {f"{m}x": round(_sharpe(pooled(best, COST_PER_SIDE * m), PPY), 2)
                   for m in (1, 2, 3)}
    cost_stress["passes"] = bool(cost_stress["3x"] > 0)
    per_asset = {s: _sharpe(tsmom_net_returns(prices[s], lookback=best), PPY) for s in prices}
    pct_pos = float(np.mean([v > 0 for v in per_asset.values()]))
    multi_asset = {"per_asset_sharpe": {k: round(v, 2) for k, v in per_asset.items()},
                   "pct_positive": pct_pos, "passes": bool(pct_pos >= 0.75)}
    best_series = config_series[best]
    dsr = deflated_sharpe_ratio(config_sharpe[best], n_trials=len(lookbacks),
                                n_obs=int(best_series.notna().sum()))
    drv = max(rets.values(), key=lambda s: s.abs().mean())
    fals = falsification_audit(drv, lambda sh: tsmom_from_returns(sh, lookback=best),
                               real_sharpe=config_sharpe[best], n_shuffles=150,
                               periods_per_year=PPY)

    passed = {
        "plateau": plateau["passes"], "pbo": pbo.get("passes"),
        "cost_stress": cost_stress["passes"], "multi_asset": multi_asset["passes"],
        "dsr": dsr["passes"], "not_falsified": not fals["falsified"],
    }
    return {"param_plateau": plateau, "pbo": pbo, "cost_stress": cost_stress,
            "multi_asset": multi_asset, "deflated_sharpe": dsr, "falsification": fals,
            "VERDICT": _verdict(passed)}
