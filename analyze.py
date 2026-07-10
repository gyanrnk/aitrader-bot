"""Show the current intelligent signals + HONEST forward accuracy from collected data.

    python analyze.py

Reads data/market/*.csv (built by the 24/7 collector), computes the latest signal per
symbol, and reports the REAL forward accuracy of past matured predictions.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aitrader.collector import analytics


def main() -> None:
    hist = analytics.load_history()
    if hist.empty:
        print("No collected data yet. Run collector.py (or wait for the GitHub Action).")
        return

    n_snaps = hist["ts"].nunique()
    print(f"History: {len(hist)} rows across {n_snaps} snapshots, "
          f"{hist['ts'].min()} to {hist['ts'].max()}\n")

    print("Current signals:")
    print(f"  {'symbol':9} {'signal':6} {'prob_up':>8} {'funding_z':>10} {'mom':>8}")
    for sym, g in hist.groupby("symbol"):
        sig = analytics.compute_signal(g)
        if sig:
            print(f"  {sym:9} {sig['signal']:6} {sig['prob_up']:>8} "
                  f"{sig['funding_z']:>10} {sig['mom']:>8.4f}")
        else:
            print(f"  {sym:9} (need more history)")

    print("\nForward accuracy (matured predictions only — the HONEST number):")
    score = analytics.score_predictions(hist)
    if score.get("scored", 0) == 0:
        print(f"  {score.get('note')}")
        print("  -> Accuracy only becomes real after ~1-2 weeks of collection. Anything")
        print("     earlier is too few samples to trust. This is by design.")
    else:
        print(f"  scored={score['scored']}  hit_rate={score['hit_rate']:.1%}  "
              f"expectancy/call={score['avg_return_per_call']:+.3%}  "
              f"{'PROFITABLE' if score['expectancy_positive'] else 'not profitable'}")
        print("  NOTE: hit_rate alone is meaningless — expectancy (net return per call) decides")
        print("  profit. 55% hits with tiny wins + big losses still loses money.")


if __name__ == "__main__":
    main()
