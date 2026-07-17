"""Perp delisting event study -> data/delist/events.csv + verdict.

    python scripts/delist_study.py [window_hours]

Bybit only (geo-blocked on GitHub US runners — run this locally).
See aitrader/research/delist_event.py for the pre-registered bar and the confound.
"""
from __future__ import annotations

import csv
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from aitrader.research.delist_event import (EVENT_FIELDS, fetch_announcements,
                                            parse_events, study_event)

OUT_DIR = os.path.join("data", "delist")
OUT = os.path.join(OUT_DIR, "events.csv")


def wmedian(v: np.ndarray, w: np.ndarray) -> float:
    if len(v) == 0 or w.sum() <= 0:
        return float("nan")
    o = np.argsort(v)
    v, w = v[o], w[o]
    return float(v[np.searchsorted(np.cumsum(w) / w.sum(), 0.5)])


def main() -> None:
    window = int(sys.argv[1]) if len(sys.argv) > 1 else 48
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Fetching delisting announcements…")
    anns = fetch_announcements()
    evs = parse_events(anns)
    print(f"  {len(anns)} announcements -> {len(evs)} single USDT-perp delistings\n")

    rows, skips = [], Counter()
    for i, ev in enumerate(evs, 1):
        r = study_event(ev, window_h=window)
        if r.get("skip"):
            # bucket by reason, not by symbol — we want to SEE what the sample lost
            skips[r["skip"].split(" (")[0]] += 1
        else:
            rows.append(r)
        if i % 20 == 0:
            print(f"  {i}/{len(evs)}  usable {len(rows)}  skipped {sum(skips.values())}")
        time.sleep(0.08)

    print("\n  --- what the sample LOST (never silent) ---")
    for reason, n in skips.most_common():
        print(f"    {n:3d}  {reason}")
    print(f"    {len(rows):3d}  USABLE  ({len(rows)/len(evs)*100:.0f}% of {len(evs)})")

    if not rows:
        print("No usable events.")
        return

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EVENT_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} events -> {OUT}")

    inc = np.array([r["incremental_pct"] for r in rows])
    pre = np.array([r["pre_abn_pct"] for r in rows])
    post = np.array([r["post_abn_pct"] for r in rows])
    turn = np.array([r["pre_turnover_usd"] for r in rows])

    print("\n" + "=" * 74)
    print(f"DELISTING EVENT STUDY — n={len(rows)}, +/-{window}h window, BTC-adjusted")
    print("=" * 74)
    print(f"  pre-announcement abnormal drift  : median {np.median(pre):+7.2f}%")
    print(f"  post-announcement abnormal drift : median {np.median(post):+7.2f}%")
    print("  " + "-" * 70)
    print(f"  INCREMENTAL (post - pre)         : median {np.median(inc):+7.2f}%   <- the only")
    print(f"                                     mean   {inc.mean():+7.2f}%      number that")
    print(f"                       VOLUME-WEIGHTED median {wmedian(inc, turn):+7.2f}%   <- DECIDES")
    print(f"  share of events negative         : {(inc < 0).mean()*100:.1f}%")
    print(f"  IQR                              : [{np.percentile(inc,25):+.2f}%, {np.percentile(inc,75):+.2f}%]")

    wm = wmedian(inc, turn)
    bar = -0.50   # -50bps round trip, pre-registered
    print("\n  PRE-REGISTERED BAR: volume-weighted median < -0.50% (round-trip cost)")
    print(f"  OBSERVED          : {wm:+.2f}%")
    print(f"  VERDICT           : {'PASS -> gauntlet' if wm < bar else 'REJECT — no capturable edge'}")

    print("\n  --- turnover distribution (is this a real market?) ---")
    for q in (10, 50, 90):
        print(f"    p{q:<2} pre-window 48h turnover: ${np.percentile(turn,q):,.0f}")


if __name__ == "__main__":
    main()
