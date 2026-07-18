"""Run the napkin test on an idea from the command line — kill it before you build it.

    python scripts/napkin.py --name "liquidation fade" \
        --mechanism "engine must close a margin-breached trader at any price" \
        --edge 1.34 --cost 5.0 --trades-per-year 1000 --capacity 25 \
        --measured --notional-weighted

    python scripts/napkin.py --examples      # show the graveyard, with real numbers

Flags you OMIT are the honest default: an edge is assumed ESTIMATED and NOT
notional-weighted unless you claim otherwise, which downgrades the verdict to UNKNOWN.
That is deliberate — `liq_meanrev` looked like +74.87bps until it was money-weighted.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aitrader.research.napkin import Idea, report

# Verified retail cost anchors, for the --cost you should actually use.
# Sources checked 2026-07-18; see PLAYBOOK.md for full citations.
COST_HINTS = """
Realistic round-trip cost (both legs). Use these, not optimism:

  crypto perp, majors, maker both sides   ~4 bps   (Bybit VIP0 maker 0.02%/side)
  crypto perp, majors, taker out          ~7 bps
  crypto perp, midcap/microcap            10-30+ bps (spread dominates, widens on stress)
  dying microcap perp                     ~50 bps  (spread when it matters)

  NOTE: negative maker fees (rebates) are VOLUME-GATED, not skill-gated.
  Kraken futures needs $250M/30d for -0.003%; Binance spot maker floors at
  +1.1bps even at VIP9 ($4B/30d). Retail NEVER reaches maker-rebate economics.
  That is why R3 is structural, not a temporary handicap.
"""


def main() -> None:
    p = argparse.ArgumentParser(description="Kill a trading idea in 60 seconds.",
                                epilog=COST_HINTS,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--examples", action="store_true", help="print the graveyard and exit")
    p.add_argument("--name", default="unnamed idea")
    p.add_argument("--mechanism", default="",
                   help="WHO pays me and WHY. Empty => auto-kill (R0).")
    p.add_argument("--edge", type=float, default=0.0, help="edge in bps per round trip")
    p.add_argument("--cost", type=float, default=0.0, help="round-trip cost in bps")
    p.add_argument("--life-h", type=float, default=None,
                   help="hours the opportunity actually persists")
    p.add_argument("--breakeven-h", type=float, default=None,
                   help="hours you must hold to amortise the cost")
    p.add_argument("--trades-per-year", type=float, default=0.0)
    p.add_argument("--capacity", type=float, default=0.0, help="USD that fits per trade")
    p.add_argument("--no-book", action="store_true",
                   help="no order reaches the book (e.g. cash settlement) -> R1")
    p.add_argument("--both-sides-forced", action="store_true",
                   help="the rule forces long AND short -> R2")
    p.add_argument("--measured", action="store_true", help="edge is OBSERVED, not estimated")
    p.add_argument("--notional-weighted", action="store_true",
                   help="edge is weighted by money, not by trade count")
    p.add_argument("--safety", type=float, default=2.0, help="required edge/cost multiple")
    a = p.parse_args()

    if a.examples:
        os.system(f'"{sys.executable}" "{os.path.join(os.path.dirname(__file__), "..", "tests", "test_napkin.py")}"')
        return

    print(report(Idea(
        name=a.name, mechanism=a.mechanism,
        edge_bps=a.edge, cost_bps=a.cost,
        opportunity_life_h=a.life_h, breakeven_hold_h=a.breakeven_h,
        trades_per_year=a.trades_per_year, capacity_usd=a.capacity,
        order_hits_book=not a.no_book, both_sides_forced=a.both_sides_forced,
        edge_is_notional_weighted=a.notional_weighted, edge_measured=a.measured,
    ), safety=a.safety))


if __name__ == "__main__":
    main()
