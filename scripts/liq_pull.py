"""Pull Kraken liquidation history -> data/liq/liquidations.csv

Usage:  python scripts/liq_pull.py [pages_per_symbol]

Newest-first walk. Re-running overwrites; this is a research pull, not the collector.
See aitrader/research/kraken_liq.py for the traps this respects.
"""
from __future__ import annotations

import csv
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aitrader.research.kraken_liq import LIQ_FIELDS, SYMBOLS, pull

OUT_DIR = os.path.join("data", "liq")
OUT = os.path.join(OUT_DIR, "liquidations.csv")


def _iso(ms):
    if not ms:
        return "?"
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="seconds")


def main():
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    os.makedirs(OUT_DIR, exist_ok=True)

    all_rows = []
    print(f"Pulling {pages} pages/symbol (~{pages * 1000:,} execs each)\n")
    for sym in SYMBOLS:
        t0 = time.time()
        r = pull(sym, max_pages=pages)
        liqs = r["liquidations"]
        all_rows.extend(liqs)
        span_h = ((r["first_ts"] or 0) - (r["last_ts"] or 0)) / 3.6e6
        pct = len(liqs) / r["n_execs"] * 100 if r["n_execs"] else 0
        print(f"{sym:12s} {r['pages']:4d}p  {r['n_execs']:7,d} execs  "
              f"{span_h:7.1f}h  ->  {len(liqs):5,d} liqs ({pct:.2f}%)  [{time.time()-t0:.0f}s]")
        print(f"{'':12s} window: {_iso(r['last_ts'])} -> {_iso(r['first_ts'])}")

    all_rows.sort(key=lambda x: x["ts"])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LIQ_FIELDS)
        w.writeheader()
        w.writerows(all_rows)

    print(f"\nWrote {len(all_rows):,} liquidations -> {OUT}")


if __name__ == "__main__":
    main()
