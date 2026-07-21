"""Net-of-cost backtest for any pluggable Strategy -> the spec's deliverable #4.

    python scripts/strategy_backtest.py [symbol] [bars] [cost_bps_per_side]

Reports total return, win rate, max drawdown, Sharpe, trade count — all NET of fees and
slippage, and always against buy & hold. A strategy that does not beat buy & hold is not
a strategy; doing nothing was cheaper and better.

Uses the same cost model as every other number in this repo (`discipline/costs.py`), so
these results are directly comparable to the gauntlet's.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from aitrader.config import Settings
from aitrader.data import get_provider
from aitrader.discipline.costs import net_returns
from aitrader.strategy import MACrossover, RSIReversion


def evaluate(name: str, w: pd.Series, close: pd.Series, cost_bps: float) -> dict:
    """Net-of-cost performance of an exposure series."""
    gross = close.pct_change().fillna(0.0)
    strat_gross = (w.shift(1).fillna(0.0) * gross)          # act on NEXT bar — no look-ahead
    net = net_returns(strat_gross, w, bps_each_side=cost_bps)

    eq = (1 + net).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    turns = (w.diff().abs() > 1e-9).sum()
    active = net[w.shift(1).fillna(0.0).abs() > 1e-9]
    ppy = 365.0
    sharpe = (net.mean() / net.std() * np.sqrt(ppy)) if net.std() > 0 else 0.0
    return {
        "strategy": name,
        "total_return": float(eq.iloc[-1] - 1),
        "sharpe": float(sharpe),
        "max_drawdown": float(dd),
        "win_rate": float((active > 0).mean()) if len(active) else 0.0,
        "n_trades": int(turns),
        "bars_in_market": float((w.abs() > 1e-9).mean()),
    }


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC-USD"
    bars = int(sys.argv[2]) if len(sys.argv) > 2 else 730          # ~2 years daily
    cost_bps = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

    print(f"Fetching {bars} bars of {symbol}…")
    df = get_provider(Settings(data_provider="yahoo")).ohlcv(symbol, lookback=bars)
    close = df["close"]
    print(f"  got {len(df)} bars: {df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d}")
    print(f"  cost model: {cost_bps} bps per side ({cost_bps * 2:.0f} bps round trip)\n")

    strategies = [MACrossover(fast=50, slow=200), RSIReversion(period=14)]

    print("=" * 78)
    print("NAPKIN GATE — run BEFORE the backtest, because that is the point")
    print("=" * 78)
    for s in strategies:
        g = s.gate()
        print(f"  {s.name:22s} {g['verdict']}")
        for k in g["kills"]:
            print(f"      X {k}")
    print()

    rows = []
    for s in strategies:
        print(f"Backtesting {s.name}…")
        w = s.weights(df, warmup=210)
        rows.append(evaluate(s.name, w, close, cost_bps))

    bh = pd.Series(1.0, index=df.index)
    rows.append(evaluate("buy & hold", bh, close, cost_bps))

    out = pd.DataFrame(rows)
    print("\n" + "=" * 78)
    print(f"NET-OF-COST RESULTS — {symbol}, {len(df)} bars")
    print("=" * 78)
    print(out.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    bh_ret = out[out.strategy == "buy & hold"].total_return.iloc[0]
    print("\n  vs buy & hold:")
    for _, r in out[out.strategy != "buy & hold"].iterrows():
        d = r.total_return - bh_ret
        print(f"    {r.strategy:22s} {d:+.1%}  {'BEATS' if d > 0 else 'LOSES TO'} buy & hold")

    print("\n  Honest reading: these are single-config results on ONE symbol. They are not")
    print("  evidence of anything until they survive the Stage-4 gauntlet (PBO, deflated")
    print("  Sharpe, cost-stress, param plateau, falsification). tsmom — the same family")
    print("  as the MA crossover — scored 3/6 there and was rejected.")


if __name__ == "__main__":
    main()
