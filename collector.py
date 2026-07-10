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

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
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


if __name__ == "__main__":
    main()
