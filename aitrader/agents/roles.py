"""The agent roles as pure functions over TradingState.

Each function is a graph node: read state, call the LLM, write a typed result back.
Mirrors TradingAgents' analyst/researcher/trader/risk-debator/PM roster.
"""
from __future__ import annotations

from ..schemas import (
    Action, Rating, AnalystReport, DebateTurn, TraderProposal, RiskDecision,
)
from ..state import TradingState


# ---------- Analysts ----------
def run_analyst(state: TradingState, role: str, llm) -> AnalystReport:
    mem = "; ".join(state.memories[:3])
    prompt = f"Analyze {state.symbol} as of {state.as_of}. Relevant past lessons: {mem or 'none'}."
    out = llm.analyze(role, prompt, state.features)
    report = AnalystReport(
        analyst=role,
        stance=float(out.get("stance", 0.0)),
        confidence=float(out.get("confidence", 0.3)),
        summary=str(out.get("summary", "")),
        evidence=list(out.get("evidence", [])),
    )
    state.reports.append(report)
    return report


# ---------- Bull / Bear researchers (debate) ----------
def run_bull(state: TradingState, llm) -> DebateTurn:
    net = state.net_stance()
    prompt = f"Bull case for {state.symbol}. Net analyst stance {net:+.2f}. Reports: " + \
             " | ".join(r.summary for r in state.reports)
    turn = DebateTurn("Bull", llm.argue("Bull", prompt), round=state.debate_count // 2 + 1)
    state.investment_debate.append(turn)
    state.debate_count += 1
    state.last_debater = "Bull"
    return turn


def run_bear(state: TradingState, llm) -> DebateTurn:
    net = state.net_stance()
    prompt = f"Bear rebuttal for {state.symbol}. Net analyst stance {net:+.2f}. " + \
             "Attack the bull thesis and name the biggest downside risk."
    turn = DebateTurn("Bear", llm.argue("Bear", prompt), round=state.debate_count // 2 + 1)
    state.investment_debate.append(turn)
    state.debate_count += 1
    state.last_debater = "Bear"
    return turn


def run_research_manager(state: TradingState, llm) -> str:
    net = state.net_stance()
    bias = "long" if net > 0.1 else "short" if net < -0.1 else "neutral"
    state.investment_plan = (
        f"Synthesized plan: lean {bias} (net stance {net:+.2f}) after "
        f"{len(state.investment_debate)} debate turns. "
        f"Bull/Bear balance considered; proceed to trader with sizing discipline."
    )
    return state.investment_plan


# ---------- Trader ----------
def run_trader(state: TradingState, llm) -> TraderProposal:
    net = state.net_stance()
    if net > 0.1:
        action = Action.BUY
    elif net < -0.1:
        action = Action.SELL
    else:
        action = Action.HOLD
    conviction = min(1.0, abs(net))
    atr_pct = state.features.get("atr_pct", 0.03)
    proposal = TraderProposal(
        action=action,
        conviction=conviction,
        thesis=state.investment_plan,
        stop_loss_pct=max(0.02, min(0.10, 2 * atr_pct)),  # stop scaled to volatility
        horizon_days=5,
    )
    state.proposal = proposal
    return proposal


# ---------- Risk debators (3-way) + Portfolio Manager ----------
def run_risk_debator(state: TradingState, persona: str, llm) -> DebateTurn:
    prompt = f"{persona} risk view on {state.proposal.action.value} {state.symbol} " \
             f"(conviction {state.proposal.conviction:.2f}, vol {state.features.get('vol_20d', 0):.3f})."
    turn = DebateTurn(persona, llm.argue(persona, prompt), round=state.risk_count // 3 + 1)
    state.risk_debate.append(turn)
    state.risk_count += 1
    state.last_risk_speaker = persona
    return turn


def run_portfolio_manager(state: TradingState, llm) -> RiskDecision:
    p = state.proposal
    conv = p.conviction
    vol = state.features.get("vol_20d", 0.02)
    # PM approves unless conviction is weak or volatility is extreme
    approved = p.action != Action.HOLD and conv >= 0.15 and vol < 0.08
    if p.action == Action.HOLD or not approved:
        rating = Rating.HOLD
    elif p.action == Action.BUY:
        rating = Rating.BUY if conv > 0.5 else Rating.OVERWEIGHT
    else:
        rating = Rating.SELL if conv > 0.5 else Rating.UNDERWEIGHT
    adj = "" if conv > 0.5 else "reduce size (low conviction)"
    if vol >= 0.08:
        adj = "blocked: volatility above risk ceiling"
    decision = RiskDecision(
        approved=approved,
        rating=rating,
        rationale=f"conviction={conv:.2f}, vol={vol:.3f}, action={p.action.value}",
        adjustments=adj,
    )
    state.risk_decision = decision
    return decision
