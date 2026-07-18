"""Back-test the napkin filter against our own graveyard.

A filter that cannot kill the ideas we ALREADY KNOW are dead is worthless. Every case
below uses the real measured numbers from `research/hypotheses.json`, and asserts both
that the idea dies AND that it dies for the right reason.

Run: python tests/test_napkin.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aitrader.research.napkin import Idea, napkin, report

# --- the graveyard: (idea, rule that must fire) ------------------------------
CASES = [
    (Idea(
        name="liq_meanrev — provide liquidity into Kraken liquidations",
        mechanism="Margin-breached traders are force-closed by the engine at any price; "
                  "I take the other side of a price-insensitive seller.",
        edge_bps=1.34,          # notional-weighted median, n=6068, $4.15M notional
        cost_bps=5.0,           # maker+taker round trip
        trades_per_year=6068 * (365 / 12),   # observed rate, annualised
        capacity_usd=25.62,     # median fill size — this is the killer
        edge_is_notional_weighted=True,
        edge_measured=True,
     ), "R3"),

    (Idea(
        name="liq_meanrev (as it looked BEFORE notional weighting)",
        mechanism="Same as above.",
        edge_bps=74.87,         # unweighted median on DOGE — looks like a goldmine
        cost_bps=5.0,
        trades_per_year=1000,
        capacity_usd=3.71,      # ...on $3.71 fills
        edge_is_notional_weighted=False,
        edge_measured=True,
     ), "R6"),

    (Idea(
        name="xexch_arb — cross-exchange funding spread",
        mechanism="Fragmented liquidity: same perp funds differently on two venues. "
                  "Long the payer, short the receiver, collect the spread.",
        edge_bps=17.3 * 100 / 365,   # SOL gross 17.3%/yr expressed per-day-ish
        cost_bps=32.0,               # 0.32% round trip = 4 legs x 8bps
        opportunity_life_h=13.8,     # longest episode EVER observed
        breakeven_hold_h=163.0,      # what the cost actually needs
        trades_per_year=42 * (365 / 2),
        capacity_usd=50_000,
        edge_is_notional_weighted=True,
        edge_measured=True,
     ), "R4"),

    (Idea(
        name="delist_event — short into forced delisting settlement",
        mechanism="Bybit force-closes every open position at a 30-min index average.",
        edge_bps=-242.0,             # incremental abnormal return came out POSITIVE (+2.42%)
        cost_bps=50.0,
        trades_per_year=193,
        capacity_usd=1_000_000,
        order_hits_book=False,       # cash settlement — R1
        both_sides_forced=True,      # zero-net-supply — R2
        edge_is_notional_weighted=True,
        edge_measured=True,
     ), "R1"),

    (Idea(
        name="tsmom — time-series momentum",
        mechanism="",                # no mechanism at all — R0
        edge_bps=0.0,
        cost_bps=10.0,
        trades_per_year=100,
        capacity_usd=100_000,
     ), "R0"),

    (Idea(
        name="funding_carry — delta-neutral carry, continuous",
        mechanism="Perp shorts pay funding to longs when funding is positive; I collect "
                  "it delta-neutral. A real cash flow, not a prediction.",
        edge_bps=0.8 * 100 / 12,     # ~0.8%/yr spread over monthly-ish turnover
        cost_bps=16.0,
        trades_per_year=12,
        capacity_usd=50_000,
        edge_is_notional_weighted=True,
        edge_measured=True,
     ), "R3"),
]


def main() -> None:
    failures = 0
    print("=" * 78)
    print("NAPKIN FILTER vs OUR OWN GRAVEYARD — every one of these is known-dead")
    print("=" * 78)
    for idea, must_fire in CASES:
        r = napkin(idea)
        fired = " ".join(r["kills"] + r["warnings"])
        ok_dead = r["verdict"] == "KILL"
        ok_rule = must_fire in fired
        status = "PASS" if (ok_dead and ok_rule) else "*** FILTER FAILED ***"
        if not (ok_dead and ok_rule):
            failures += 1
        print(f"\n[{status}] expected rule {must_fire}")
        print(report(idea))

    # --- control: a hypothetical idea that SHOULD survive ---------------------
    good = Idea(
        name="CONTROL — a hypothetical idea that should NOT be killed",
        mechanism="Someone is contractually obliged to pay me a fee for a service.",
        edge_bps=60.0, cost_bps=10.0,
        opportunity_life_h=200.0, breakeven_hold_h=20.0,
        trades_per_year=50, capacity_usd=100_000,
        edge_is_notional_weighted=True, edge_measured=True,
    )
    r = napkin(good)
    ok = r["verdict"] == "PASS"
    if not ok:
        failures += 1
    print(f"\n[{'PASS' if ok else '*** FILTER FAILED — kills everything ***'}] control must survive")
    print(report(good))

    print("\n" + "=" * 78)
    if failures:
        print(f"{failures} FILTER FAILURES — the napkin test is not trustworthy yet")
        sys.exit(1)
    print("All graveyard cases killed for the right reason; control survived.")
    print("The filter reproduces every rejection we spent a week discovering.")


if __name__ == "__main__":
    main()
