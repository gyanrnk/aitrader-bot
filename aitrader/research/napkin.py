"""The napkin test — kill an idea in 60 seconds, before writing any code.

WHY THIS EXISTS: we have tested and rejected 5 ideas. Each took hours-to-days of
implementation, and EVERY ONE could have been killed up front by arithmetic we already
knew. This module turns that arithmetic into a function, so the filter is mechanical
instead of a thing we remember to apply.

The rules below are not theory. Each one is a post-mortem of a specific dead idea:

  R1  settle != trade        <- delist_event. We called forced cash settlement "the purest
                                forced flow that exists". Nobody's order hits the book.
  R2  zero-net-supply        <- delist_event. A perp has one short per long; if a rule
                                forces BOTH sides, net flow is zero by construction.
  R3  edge vs cost           <- liq_meanrev (+1.34bps vs 5bps), funding_carry (0.8%/yr).
                                The single most common cause of death.
  R4  life vs breakeven      <- xexch_arb. Spread lived 13.8h; cost needed 163h to
                                amortise. Short by 12x.
  R5  notional weighting     <- liq_meanrev. Unweighted median said +74.87bps and looked
                                like a goldmine; the money-weighted number was +1.34bps,
                                because the big discounts were on $3.71 scraps.
  R6  capacity               <- 74bps on a $3.71 fill is $0.03/trade. A real edge that
                                cannot absorb capital is a hobby, not a strategy.
  R7  the barrier            <- measured 2026-07-18: our latency to OKX/Bybit/Kraken is
                                82-211ms from a home connection. A colocated firm sits at
                                ~0.2ms; HFT measures in nanoseconds. We are 400-1000x
                                slower, and our collector polls every 10 MINUTES. So the
                                question "what stops this being arbed away?" decides
                                everything. If the answer is SPEED, we lost before we
                                could see it. If it is a STRUCTURAL constraint (borrow
                                quota, capital, access, mandate) we may be inside it.
                                And if you cannot name a barrier at all, either the edge
                                is not real or you are the one about to be arbed.

                                Our own record backs this: xexch_arb (13.8h life) and
                                liq_meanrev (a queue-position race) died; the sole
                                survivor, funding_escalation, runs 26h episodes gated by
                                borrow quota — slowness costs nothing there.

USAGE
    from aitrader.research.napkin import Idea, napkin
    print(napkin(Idea(name="...", mechanism="...", edge_bps=1.34, cost_bps=5.0, ...)))

If it returns KILL, do not build it. If it returns PASS, it has earned a gauntlet run —
not a deployment.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Require edge to CLEAR cost by this factor, not merely match it. Justification:
#   * quoted cost is the optimistic case — spread widens exactly when you want to trade
#   * slippage grows with size, and measured edge usually comes from small fills
#   * a strategy sitting at edge == cost is a coin flip on execution quality alone
SAFETY_FACTOR = 2.0


@dataclass
class Idea:
    """One trading idea, described in the terms that actually decide its fate."""

    name: str
    mechanism: str                      # "who pays me, and why?" — empty = auto-kill

    # --- the money ---
    edge_bps: float                     # per round trip, NOTIONAL-WEIGHTED (see R5)
    cost_bps: float                     # per round trip: fees + spread + slippage, both legs

    # --- timing (optional; only for ideas that require holding) ---
    opportunity_life_h: float | None = None   # how long the dislocation actually persists
    breakeven_hold_h: float | None = None     # how long you must hold to amortise cost

    # --- scale ---
    trades_per_year: float = 0.0
    capacity_usd: float = 0.0           # capital that fits per trade without moving price

    # --- structural sanity (R1/R2) ---
    order_hits_book: bool = True        # does anyone actually place an order? (cash settle = No)
    both_sides_forced: bool = False     # if a rule forces long AND short, net flow is zero

    # --- the barrier (R7) — why has this not already been arbed away? ---
    barrier: str = ""                   # name it. empty => you cannot explain persistence
    wins_by_being_first: bool = False   # is the edge a speed race? we are 400-1000x slow

    # --- honesty flags ---
    edge_is_notional_weighted: bool = False   # False => the edge number is not trustworthy
    edge_measured: bool = False               # False => it is an estimate, not an observation

    notes: str = ""
    _checks: list = field(default_factory=list, repr=False)


def _annual_return_pct(idea: Idea) -> float:
    """Gross annual return on deployed capital, before the edge/cost check."""
    net_bps = idea.edge_bps - idea.cost_bps
    return net_bps * idea.trades_per_year / 100.0


def napkin(idea: Idea, safety: float = SAFETY_FACTOR) -> dict:
    """Run every kill rule. Returns a verdict dict; `verdict` is KILL / PASS / UNKNOWN."""
    kills: list[str] = []
    warns: list[str] = []

    # ---- R1: does an order actually reach the order book? -------------------
    if not idea.order_hits_book:
        kills.append(
            "R1 settle!=trade: nobody puts an order on the book (cash settlement at an "
            "index touches no book). There is no flow to provide and no impact to fade.")

    # ---- R2: zero-net-supply ------------------------------------------------
    if idea.both_sides_forced:
        kills.append(
            "R2 zero-net-supply: the rule forces BOTH sides. Every long is matched by a "
            "short, so net flow is zero by construction — however dramatic the rule sounds.")

    # ---- R0: mechanism required (RESEARCH_GUIDE's one question) -------------
    if not idea.mechanism.strip():
        kills.append(
            "R0 no mechanism: cannot name who pays me and why. That is pattern-matching, "
            "and every pattern-based idea we tested failed.")

    # ---- R3: edge vs cost — the most common cause of death ------------------
    required = idea.cost_bps * safety
    if idea.edge_bps <= 0:
        kills.append(f"R3 edge<=0: measured edge is {idea.edge_bps:+.2f}bps. There is nothing to capture.")
    elif idea.edge_bps < required:
        kills.append(
            f"R3 edge<cost: {idea.edge_bps:.2f}bps edge vs {idea.cost_bps:.2f}bps cost "
            f"(need >{required:.2f}bps at {safety:g}x safety). Net "
            f"{idea.edge_bps - idea.cost_bps:+.2f}bps per round trip.")

    # ---- R4: does the opportunity outlive its own breakeven? ----------------
    if idea.opportunity_life_h is not None and idea.breakeven_hold_h is not None:
        if idea.opportunity_life_h < idea.breakeven_hold_h:
            short_by = idea.breakeven_hold_h / max(idea.opportunity_life_h, 1e-9)
            kills.append(
                f"R4 life<breakeven: opportunity lives {idea.opportunity_life_h:.1f}h but "
                f"cost needs {idea.breakeven_hold_h:.1f}h to amortise — short by {short_by:.1f}x. "
                "You pay the round trip far more often than you collect.")

    # ---- R5: is the edge where the MONEY is, or only where the trades are? --
    if not idea.edge_is_notional_weighted:
        warns.append(
            "R5 unweighted: edge is not notional-weighted, so it is not yet trustworthy. "
            "An unweighted median counts a $3 fill the same as a $50,000 one — that is how "
            "liq_meanrev looked like +74.87bps when the money-weighted truth was +1.34bps.")
    if not idea.edge_measured:
        warns.append("R5b estimated: edge is an estimate, not an observation. Measure it before building.")

    # ---- R7: what stops this being arbed away? ------------------------------
    if idea.wins_by_being_first:
        kills.append(
            "R7 speed race: the edge goes to whoever is first. Measured latency from here "
            "is 82-211ms vs ~0.2ms colocated — we are 400-1000x slower, and our collector "
            "polls every 10 MINUTES. This is lost before we can see it.")
    if not idea.barrier.strip():
        kills.append(
            "R7 no barrier: cannot name what stops this being arbed away. Either the edge "
            "is not real, or we are the one about to be arbed. Every surviving edge has an "
            "explanation for why it survives — name it or drop it.")

    # ---- R6: capacity — can this absorb capital? ----------------------------
    annual_pct = _annual_return_pct(idea)
    if idea.capacity_usd and idea.capacity_usd < 100:
        kills.append(
            f"R6 capacity: only ${idea.capacity_usd:,.2f} fits per trade. A real edge that "
            "cannot absorb capital is a hobby — 74bps on a $3.71 fill is $0.03 a trade.")
    elif idea.trades_per_year and idea.capacity_usd:
        annual_usd = idea.capacity_usd * annual_pct / 100.0
        if 0 < annual_usd < 500:
            warns.append(
                f"R6 thin: ~${annual_usd:,.0f}/yr on ${idea.capacity_usd:,.0f} of capital. "
                "Real, but is it worth the operational risk of running live?")

    verdict = "KILL" if kills else ("PASS" if idea.edge_measured and
                                    idea.edge_is_notional_weighted else "UNKNOWN")
    return {
        "name": idea.name,
        "verdict": verdict,
        "net_bps_per_trade": round(idea.edge_bps - idea.cost_bps, 2),
        "annual_return_pct": round(annual_pct, 2) if idea.trades_per_year else None,
        "kills": kills,
        "warnings": warns,
    }


def report(idea: Idea, safety: float = SAFETY_FACTOR) -> str:
    """Human-readable verdict."""
    r = napkin(idea, safety)
    icon = {"KILL": "KILL", "PASS": "PASS", "UNKNOWN": "UNKNOWN"}[r["verdict"]]
    lines = [f"[{icon}] {r['name']}",
             f"  net per round trip : {r['net_bps_per_trade']:+.2f} bps"]
    if r["annual_return_pct"] is not None:
        lines.append(f"  annual return      : {r['annual_return_pct']:+.2f} %")
    for k in r["kills"]:
        lines.append(f"  X {k}")
    for w in r["warnings"]:
        lines.append(f"  ! {w}")
    if not r["kills"] and not r["warnings"]:
        lines.append("  no rule fired — earns a gauntlet run, NOT a deployment")
    return "\n".join(lines)
