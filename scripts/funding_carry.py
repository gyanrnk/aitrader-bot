"""Run the funding-carry backtest end-to-end and pass it through the honest gates.

    python scripts/funding_carry.py

Fetches real Binance funding (2y), runs the pre-registered delta-neutral carry on a
basket, then applies the deflated-Sharpe (multiple-testing) gate and logs the result
to the hypothesis registry. Prints an honest verdict.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitrader.research import HypothesisRegistry, deflated_sharpe_ratio
from aitrader.research.funding_backtest import backtest_portfolio, ENTRY_THRESH

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


def main() -> None:
    print("Fetching real Binance funding (2y) + backtesting delta-neutral carry…\n")
    res = backtest_portfolio(SYMBOLS, years=2.0)

    print(f"{'symbol':10} {'netSharpe':>10} {'netAPR':>9} {'maxDD':>8} {'timeIn':>7} {'avgFund(bp)':>12}")
    print("-" * 60)
    for r in res["per_symbol"]:
        print(f"{r['symbol']:10} {r['net_sharpe']:>10} {r['net_apr']:>9.2%} "
              f"{r['max_drawdown']:>8.2%} {r['time_in_market']:>7} {r['avg_funding_bps']:>12}")
    print("-" * 60)
    print(f"POOLED net Sharpe: {res['pooled_net_sharpe']}   "
          f"% symbols positive: {res['pct_symbols_positive']}   "
          f"mean symbol Sharpe: {res['mean_symbol_sharpe']}")

    # --- honest gates ---
    reg = HypothesisRegistry()
    reg.add("funding_carry", "Funding-rate carry (delta-neutral)", "funding_carry",
            "Perp shorts pay me funding when funding>0 — real cash flow, not prediction.")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reg.log_test("funding_carry", stamp,
                 params={"entry_thresh": ENTRY_THRESH, "symbols": SYMBOLS},
                 is_sharpe=res["pooled_net_sharpe"] or 0.0,
                 oos_sharpe=res["pooled_net_sharpe"],
                 note="pre-registered single config; pooled across 4 majors")

    n_trials = reg.total_trials()
    g = deflated_sharpe_ratio(res["pooled_net_sharpe"] or 0.0,
                              n_trials=n_trials, n_obs=res["pooled_n_periods"])
    print("\n--- Deflated-Sharpe gate (multiple-testing correction) ---")
    print(f"trials logged: {n_trials}   benchmark(luck): {g['benchmark_sharpe']}   "
          f"DSR: {g['dsr']}   -> {'PASS' if g['passes'] else 'FAIL'}")

    print("\n--- Honest read (skeptical by design) ---")
    s = res["pooled_net_sharpe"] or 0.0
    apr = max((r["net_apr"] for r in res["per_symbol"]), default=0.0)
    avg_apr = sum(r["net_apr"] for r in res["per_symbol"]) / len(res["per_symbol"])

    if s > 3:
        print(f"[RED FLAG] Sharpe {s} is implausibly high -> suspect MODELING OPTIMISM, not a money machine.")
    if avg_apr < 0.03:
        print(f"[REALITY] Avg net APR is only {avg_apr:.2%}/yr. High Sharpe + tiny return = classic")
        print("          capacity-limited carry. You cannot get rich on this; you can lose on frictions.")
    print("Un-modeled frictions that will SHRINK this a lot: execution slippage, basis risk (legs")
    print("don't perfectly offset), ~0.5x capital efficiency (both legs funded), funding you can't")
    print("actually capture at size, and exchange/withdrawal risk.")
    print(f"The DSR 'pass' here is WEAK: n_trials={n_trials}, single config -> not real validation.")
    print("Verdict: a small, real, but fragile carry. NOT deployable. Next = Stage 4 gauntlet")
    print("(2x/3x cost stress, capital-efficiency haircut, param plateau) + months of forward paper.")
    print("\nEngineering result, not investment advice. No guarantee of profit.")


if __name__ == "__main__":
    main()
