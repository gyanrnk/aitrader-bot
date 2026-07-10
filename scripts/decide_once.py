"""Run one full decision cycle for a symbol and print the reasoning trail.

    python scripts/decide_once.py AAPL
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitrader.runner import TradingBot


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "MOCKX"
    bot = TradingBot()
    decision, state = bot.decide(symbol)

    print(f"\n=== {symbol}  (mode={bot.settings.mode}, data={bot.settings.data_provider}) ===")
    print("Features:", {k: round(v, 4) for k, v in state.features.items()})
    print("\n-- Analyst reports --")
    for r in state.reports:
        print(f"  [{r.analyst:12}] stance={r.stance:+.2f} conf={r.confidence:.2f} :: {r.summary}")
    print("\n-- Investment debate --")
    for t in state.investment_debate:
        print(f"  ({t.round}) {t.speaker}: {t.argument}")
    print("  plan:", state.investment_plan)
    print("\n-- Risk debate --")
    for t in state.risk_debate:
        print(f"  ({t.round}) {t.speaker}: {t.argument}")
    print("\n-- Portfolio Manager --")
    print(" ", state.risk_decision)

    print("\n>>> DECISION:", decision)
    fill = bot.execute(decision, price=state.features["price"])
    print(">>> FILL:", fill)


if __name__ == "__main__":
    main()
