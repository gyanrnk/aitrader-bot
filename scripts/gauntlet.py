"""Run the Stage 4 Validation Gauntlet on the funding-carry candidate.

    python scripts/gauntlet.py

All checks are free (pure computation on already-cached data). Prints an honest,
per-check pass/fail and the final deployable verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitrader.research.gauntlet import run_gauntlet

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


def main() -> None:
    print("Stage 4 — Validation Gauntlet on funding-carry (free, cached data)...\n")
    res = run_gauntlet(SYMBOLS, years=2.0)

    def line(name, passed, extra=""):
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:14} {extra}")

    p = res["param_plateau"]
    line("param_plateau", p["passes"],
         f"{int(p['positive_frac']*100)}% configs positive, best spike x{p['spike_vs_pos_median']} vs pos-median")
    pbo = res["pbo"]
    line("PBO", pbo.get("passes"), f"PBO={pbo.get('pbo')} (want <0.5)")
    cs = res["cost_stress"]
    line("cost_stress", cs["passes"], f"1x={cs['1x']} 2x={cs['2x']} 3x={cs['3x']} Sharpe")
    ma = res["multi_asset"]
    line("multi_asset", ma["passes"], f"{int(ma['pct_positive']*100)}% assets positive")
    d = res["deflated_sharpe"]
    line("deflated_sharpe", d["passes"], f"DSR={d['dsr']} vs luck-benchmark {d['benchmark_sharpe']}")
    f = res["falsification"]
    line("not_falsified", not f["falsified"],
         f"p={f['p_value']} (null mean Sharpe {f['null_mean_sharpe']})")

    v = res["VERDICT"]
    print(f"\n  ==> {v['checks_passed']} checks passed. DEPLOYABLE: {v['deployable']}")

    print("\n--- Honest read ---")
    if v["deployable"]:
        print("Survived the gauntlet. Next = forward paper test (3+ months), NOT live money yet.")
    else:
        failed = [k for k, ok in v["detail"].items() if not ok]
        print(f"FAILED checks: {failed}")
        print("This is the gauntlet doing its job. A candidate that fails here would have LOST")
        print("money live. Correct outcome: do NOT deploy; record it and iterate honestly.")
    print("\nEngineering result, not investment advice. No guarantee of profit.")


if __name__ == "__main__":
    main()
