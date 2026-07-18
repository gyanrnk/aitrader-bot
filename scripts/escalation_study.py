"""Reconstruct OKX funding-escalation episodes from history -> data/escalation/episodes.csv

    python scripts/escalation_study.py [max_symbols]

Applies the bar pre-registered in research/hypotheses.json (funding_escalation) to
capture_bps — the funding available AFTER escalation is observable — never to total_bps.
"""
from __future__ import annotations

import csv
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from aitrader.research.escalation import (EPISODE_FIELDS, all_swaps, episodes,
                                          history, verdict)

OUT_DIR = os.path.join("data", "escalation")
OUT = os.path.join(OUT_DIR, "episodes.csv")


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    os.makedirs(OUT_DIR, exist_ok=True)

    syms = all_swaps()[:limit]
    print(f"Scanning {len(syms)} OKX swaps for escalation episodes…\n")

    eps, scanned, no_hist = [], 0, 0
    for i, s in enumerate(syms, 1):
        rows = history(s)
        if len(rows) < 6:
            no_hist += 1
        else:
            scanned += 1
            eps.extend(episodes(s, rows))
        if i % 50 == 0:
            print(f"  {i}/{len(syms)}  scanned {scanned}  episodes {len(eps)}")
        time.sleep(0.05)

    print(f"\n  scanned {scanned} symbols with history ({no_hist} without)")
    if not eps:
        print("No escalation episodes found.")
        return

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EPISODE_FIELDS)
        w.writeheader()
        w.writerows(eps)
    print(f"  wrote {len(eps)} episodes -> {OUT}")

    v = verdict(eps)
    span = (max(e["end_ts"] for e in eps) - min(e["start_ts"] for e in eps)) / 8.64e7

    print("\n" + "=" * 74)
    print(f"FUNDING-ESCALATION EPISODES — n={v['n']} across {scanned} symbols, ~{span:.0f}d")
    print("=" * 74)
    print(f"  median duration                  : {v['median_duration_h']:.1f} h")
    print(f"  median TRIGGER funding (not ours): {v['median_trigger_bps']:+.2f} bps")
    print(f"  median CAPTURE funding (tradeable): {v['median_capture_bps']:+.2f} bps  <- the bar applies here")
    print(f"  mean   CAPTURE funding           : {v['mean_capture_bps']:+.2f} bps")
    print(f"  share of episodes clearing {v['bar_bps']:.0f}bps : {v['pct_clearing_bar']*100:.1f}%")
    print()
    print(f"  TIMING CHECK — share of the money sitting in the TRIGGER settlement:")
    print(f"    {v['pct_of_money_in_trigger']*100:.1f}%")
    print("    (high => the fat funding is paid BEFORE escalation is visible => unlearnable)")
    print()
    print(f"  PRE-REGISTERED BAR : capture > {v['bar_bps']:.0f} bps")
    print(f"  VERDICT            : {v['verdict']}")

    cap = np.array([e["capture_bps"] for e in eps])
    print("\n  capture_bps distribution:")
    for q in (10, 25, 50, 75, 90, 99):
        print(f"    p{q:<2}: {np.percentile(cap, q):+8.2f} bps")
    best = max(eps, key=lambda e: e["capture_bps"])
    print(f"\n  best single episode: {best['inst_id']} "
          f"{best['capture_bps']:+.1f}bps over {best['duration_h']}h "
          f"({best['n_settlements']} settlements at {best['min_interval_h']}h)")


if __name__ == "__main__":
    main()
