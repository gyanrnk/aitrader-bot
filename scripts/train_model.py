"""Train + honestly evaluate the ML predictor.

    python scripts/train_model.py                 # mock data (offline)
    python scripts/train_model.py BTC-USD yfinance # real data (needs internet)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitrader.config import load_settings, Settings
from aitrader.data import get_provider
from aitrader.models.train import train_and_eval


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "MOCKX"
    provider_name = sys.argv[2] if len(sys.argv) > 2 else None

    settings = load_settings()
    if provider_name:
        settings = Settings(data_provider=provider_name)
    ohlcv = get_provider(settings).ohlcv(symbol, lookback=1500)

    save_path = Path(__file__).resolve().parents[1] / "models_store" / f"{symbol}.pkl"
    report, _ = train_and_eval(ohlcv, horizon=5, n_splits=5, save_path=save_path)

    print(json.dumps(report, indent=2, default=str))
    print("\n--- How to read this ---")
    print("cv_accuracy_mean : directional accuracy (52-55% is already good; >60% suspect leakage)")
    print("cv_auc_mean      : ranking quality (0.5 = coin flip, >0.55 = real signal)")
    print("oos_net_sharpe   : THE number that matters — risk-adjusted return NET of cost")
    print("  -> accuracy without a positive net Sharpe = no tradable edge.")


if __name__ == "__main__":
    main()
