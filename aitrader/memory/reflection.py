"""Reflection loop: turn realized outcomes into new long-term memories.

FinMem `reflection.py` idea, closing the learn-from-outcome loop: after a trade is
resolved, write a durable lesson ("shorting into earnings on thin volume lost 3x")
so the next similar setup recalls it. In `live` mode you'd have an LLM summarize;
the mock version writes a crisp templated lesson.
"""
from __future__ import annotations

from ..schemas import Action, FinalDecision


def reflect_on_trade(
    decision: FinalDecision,
    realized_return: float,
    memory,                # LayeredMemory
    llm=None,              # optional live LLM client
) -> str:
    """Store a reflection memory keyed to the decision; return the lesson text."""
    outcome = "WON" if realized_return > 0 else "LOST"
    base = (
        f"{decision.symbol}: {decision.action.value} (rating {decision.rating.value}, "
        f"conviction {decision.conviction:.2f}) {outcome} "
        f"{realized_return:+.2%}. Reason was: {decision.reason}"
    )
    if llm is not None:
        lesson = llm.reflect(base)     # live: LLM distills a transferable lesson
    else:
        # Mock: reinforce or warn depending on outcome.
        verb = "Confirmed" if realized_return > 0 else "Caution"
        lesson = f"{verb}: {base}"
    # winners/losers that were high-conviction are the most important to remember
    importance = 70 + 25 * abs(realized_return) * (1 if realized_return < 0 else 0.5)
    memory.add(lesson, layer="reflection", importance=min(importance, 100.0))
    return lesson
