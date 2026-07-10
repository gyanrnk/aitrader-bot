"""Stage 1 CLI — hypothesis registry + multiple-testing gate.

    python scripts/hypothesis.py seed          # register the 4 candidate families
    python scripts/hypothesis.py list           # show registry + total trials
    python scripts/hypothesis.py gate 0.35 250 10   # observed_sharpe n_obs n_trials
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitrader.research import HypothesisRegistry, deflated_sharpe_ratio

# Economically-justified, retail-accessible families (someone pays you a real cash flow).
CANDIDATES = [
    ("funding_carry", "Funding-rate carry (delta-neutral)", "funding_carry",
     "Spot long + perp short when funding is high: the perp shorts PAY me the funding. "
     "Real recurring cash flow, not a price prediction."),
    ("basis_conv", "Basis convergence", "basis",
     "Perp/futures price converges to spot at/over time; capture the spread as it closes."),
    ("liq_meanrev", "Liquidation-cascade mean reversion", "liq_meanrev",
     "Forced liquidations overshoot price; I provide liquidity into the cascade and fade it."),
    ("vol_momo_alts", "Vol-filtered momentum on mid-cap alts", "vol_momo",
     "Institutions avoid small caps for capacity reasons, leaving momentum less arbitraged; "
     "trade it only in calm-vol regimes to cut whipsaw."),
]


def seed(reg: HypothesisRegistry) -> None:
    for id, name, fam, why in CANDIDATES:
        reg.add(id, name, fam, why)
    print(f"Seeded {len(CANDIDATES)} hypotheses. {reg.summary()}")


def show(reg: HypothesisRegistry) -> None:
    s = reg.summary()
    print(f"Hypotheses: {s['hypotheses']} | total trials so far: {s['total_trials']}")
    print(f"By status: {s['by_status']}\n")
    for h in reg.items.values():
        print(f"[{h.status:8}] {h.id:14} {h.name}")
        print(f"           WHY: {h.economic_rationale[:90]}")
        if h.tests:
            print(f"           tests: {len(h.tests)}  best OOS Sharpe: {h.best_oos_sharpe}")


def gate(observed: float, n_obs: int, n_trials: int) -> None:
    r = deflated_sharpe_ratio(observed, n_trials=n_trials, n_obs=n_obs)
    print(f"Observed Sharpe : {observed}")
    print(f"Trials counted  : {n_trials}   (the more you tried, the higher the bar)")
    print(f"Benchmark (luck): {r['benchmark_sharpe']}   <- you must BEAT this, not 0")
    print(f"Deflated Sharpe : {r['dsr']}   = P(edge is real)")
    print(f"VERDICT         : {'PASS (DSR>=0.95)' if r['passes'] else 'FAIL - likely noise'}")


def main() -> None:
    reg = HypothesisRegistry()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "seed":
        seed(reg)
    elif cmd == "gate":
        observed = float(sys.argv[2]) if len(sys.argv) > 2 else 0.35
        n_obs = int(sys.argv[3]) if len(sys.argv) > 3 else 250
        n_trials = int(sys.argv[4]) if len(sys.argv) > 4 else max(reg.total_trials(), 1)
        gate(observed, n_obs, n_trials)
    else:
        show(reg)


if __name__ == "__main__":
    main()
