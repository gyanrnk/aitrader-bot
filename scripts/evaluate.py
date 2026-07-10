"""The scoreboard. Run the pipeline across a BASKET of markets and log the result.

This is how we decide whether any change is a REAL improvement: a change is only
"better" if it lifts the net-of-cost Sharpe across most of the basket, not one lucky
market. Every run is appended to results/experiments.jsonl with a label so you can
compare experiments over time and catch yourself overfitting to one symbol.

    python scripts/evaluate.py "baseline"
    python scripts/evaluate.py "added_funding_feature" BTC-USD ETH-USD SPY AAPL
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitrader.config import Settings
from aitrader.data import get_provider
from aitrader.models.train import train_and_eval, train_and_eval_meta

USE_META = os.getenv("AITRADER_META", "0") == "1"
USE_ALTDATA = os.getenv("AITRADER_ALTDATA", "0") == "1"

DEFAULT_BASKET = ["BTC-USD", "ETH-USD", "SPY", "AAPL"]
ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "results" / "experiments.jsonl"


def evaluate(label: str, symbols: list[str]) -> dict:
    settings = Settings(data_provider="yfinance")
    provider = get_provider(settings)
    rows = []
    for sym in symbols:
        try:
            ohlcv = provider.ohlcv(sym, lookback=1500)
            if USE_META:
                rep, _ = train_and_eval_meta(ohlcv, horizon=5, n_splits=5)
            else:
                extra = None
                if USE_ALTDATA:
                    from aitrader.data.altdata import binance_funding_daily
                    extra = binance_funding_daily(sym)
                    if extra is None:
                        rows.append({"symbol": sym, "error": "no funding data (not crypto / unreachable)"})
                        continue
                rep, _ = train_and_eval(ohlcv, horizon=5, n_splits=5, extra=extra)
            rows.append({
                "symbol": sym,
                "acc": rep["cv_accuracy_mean"],
                "auc": rep["cv_auc_mean"],
                "net_sharpe": rep["oos_net_sharpe"],
                "net_return": rep["oos_net_total_return"],
                "max_dd": rep["oos_max_drawdown"],
                "trades": rep.get("trade_fraction", 1.0),
            })
        except Exception as e:
            rows.append({"symbol": sym, "error": str(e)[:80]})

    ok = [r for r in rows if "net_sharpe" in r and r["net_sharpe"] is not None]
    sharpes = [r["net_sharpe"] for r in ok]
    summary = {
        "label": label,
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "symbols": symbols,
        "mean_net_sharpe": round(sum(sharpes) / len(sharpes), 3) if sharpes else None,
        "pct_positive_sharpe": round(sum(s > 0 for s in sharpes) / len(sharpes), 2) if sharpes else None,
        "pct_beats_gate": round(sum(s > 1.0 for s in sharpes) / len(sharpes), 2) if sharpes else None,
        "rows": rows,
    }
    return summary


def _fmt(v) -> str:
    return f"{v:>8}" if v is not None else f"{'NA':>8}"


def _print_table(summary: dict) -> None:
    mode = "META-LABELING" if USE_META else ("price+FUNDING" if USE_ALTDATA else "price only")
    acc_hdr, auc_hdr = ("tradeAcc", "primAcc") if USE_META else ("acc", "auc")
    print(f"\n=== Experiment: {summary['label']}  [{mode}]  ({summary['utc']}) ===")
    print(f"{'symbol':10} {acc_hdr:>8} {auc_hdr:>8} {'netSharpe':>10} {'netRet':>8} {'maxDD':>8} {'trades':>7}")
    print("-" * 62)
    for r in summary["rows"]:
        if "error" in r:
            print(f"{r['symbol']:10} ERROR: {r['error']}")
            continue
        print(f"{r['symbol']:10} {_fmt(r['acc'])} {_fmt(r['auc'])} "
              f"{_fmt(r['net_sharpe'])} {_fmt(r['net_return'])} {_fmt(r['max_dd'])} {r.get('trades', 1.0):>7}")
    print("-" * 62)
    print(f"MEAN net Sharpe: {summary['mean_net_sharpe']}   "
          f"% positive: {summary['pct_positive_sharpe']}   "
          f"% pass gate(>1): {summary['pct_beats_gate']}")
    verdict = "REAL IMPROVEMENT candidate" if (summary["mean_net_sharpe"] or -9) > 0 \
        else "no tradable edge (as expected on price-only features)"
    print(f"VERDICT: {verdict}")


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    default = ["BTC-USD", "ETH-USD"] if USE_ALTDATA else DEFAULT_BASKET
    symbols = sys.argv[2:] if len(sys.argv) > 2 else default
    summary = evaluate(label, symbols)
    _print_table(summary)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(summary) + "\n")
    print(f"\nlogged -> {LOG.relative_to(ROOT)}  (compare experiments with: cat {LOG.name})")


if __name__ == "__main__":
    main()
