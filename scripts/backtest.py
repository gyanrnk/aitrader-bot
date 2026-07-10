"""Walk-forward backtest with the discipline scorecard.

    python scripts/backtest.py MOCKX
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitrader.config import load_settings
from aitrader.data import get_provider
from aitrader.backtest import Backtester


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "MOCKX"
    settings = load_settings()
    ohlcv = get_provider(settings).ohlcv(symbol, lookback=400)

    report = Backtester(settings).run(symbol, ohlcv)
    print(json.dumps(report, indent=2, default=str))

    print("\n--- Verdict ---")
    print("Beats buy & hold (net of cost):", report["beats_buy_and_hold"])
    crit = [f for f in report["overfit_flags"] if f["severity"] == "critical"]
    print("Overfit red flags:", crit or "none")


if __name__ == "__main__":
    main()
