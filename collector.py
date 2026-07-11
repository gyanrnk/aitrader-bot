"""Append one market snapshot to daily CSV storage. Run on a schedule (24/7).

    python collector.py

Storage: data/market/YYYY-MM-DD.csv (one file per UTC day, appended each run).
Runs on GitHub Actions cron (free, no PC needed) or locally / on a VPS.
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aitrader.collector import fetch_snapshot, FIELDS
from aitrader.collector import analytics

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]  # Kraken perps (US-accessible)
STORE = Path(__file__).resolve().parent / "data" / "market"


def main() -> None:
    rows = fetch_snapshot(SYMBOLS)
    if not rows:
        print("No data fetched (source unreachable). Nothing written.")
        return
    STORE.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = STORE / f"{day}.csv"
    new_file = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {path.relative_to(STORE.parent.parent)}")
    for r in rows:
        print(f"  {r['symbol']:9} ${r['price']:>10,.2f}  funding {r['funding']*100:+.4f}%  "
              f"OI {r['open_interest']:,.0f}")

    # --- intelligence layer: compute signals, log predictions, score matured ones ---
    hist = analytics.load_history()
    logged = analytics.log_predictions(hist)
    if logged:
        print("Signals logged:", ", ".join(f"{r['symbol']}={r['signal']}" for r in logged))
    else:
        print("Signals: not enough history yet (builds over time).")
    score = analytics.score_predictions(hist)
    print("Forward accuracy:", score)

    # --- forward paper-trade with fake money (the real test) ---
    from aitrader.collector import paper
    pnl = paper.mark_and_trade(hist, analytics)
    print("Paper P&L:", pnl)


if __name__ == "__main__":
    main()
