# Architecture

Three layers, each borrowing a proven logic from an open-source reference and
adapted here into one coherent, runnable system.

```
        ┌── DATA (data/) ───────────────────────────────────────────────┐
        │  provider interface -> mock | yfinance ; indicators (RSI/MACD) │
        └───────────────────────────────┬───────────────────────────────┘
                                         │ point-in-time features
   ┌─────────────────── ORCHESTRATION (orchestration/graph.py) ──────────┐
   │  analysts(market,news,sentiment,fundamentals)                        │
   │        → Bull ⇄ Bear debate (bounded)   → research manager           │
   │        → trader proposal                                             │
   │        → Aggressive/Conservative/Neutral risk debate → PM decision   │
   │            ▲ recall (sim+recency+importance)      │                  │
   │      ┌─────┴──── MEMORY (memory/) ──────┐         │ reflect          │
   │      │ layered · exponential decay      │◄────────┘ on outcome       │
   └──────┴──────────────────┬───────────────┴────────────────────────────┘
                             │ FinalDecision (typed, net-of-cost sized)
        ┌── RISK (risk/) ────▼──────┐        ┌── EXECUTION (execution/) ──┐
        │ risk-per-trade + caps     │───────▶│ paper (default) | ccxt     │
        └───────────────────────────┘        └────────────────────────────┘

        ┌── DISCIPLINE (discipline/)  — gates every backtest/report ──────┐
        │  net-of-cost P&L · leakage firewall · beat baselines ·          │
        │  reward-hacking / IS-vs-OOS overfit detection                   │
        └─────────────────────────────────────────────────────────────────┘
```

## Layer 1 — Orchestration (from TradingAgents)
- **Role decomposition as a graph** (`orchestration/graph.py`): specialist nodes pass
  a typed `TradingState`, instead of one monolithic prompt.
- **Bounded adversarial debate** (`orchestration/conditional_logic.py`): a Bull and a
  Bear argue for a fixed number of rounds before anyone decides — every thesis must
  survive a rebuttal. Risk is a separate **3-way** debate (Aggressive/Conservative/
  Neutral) resolved by a Portfolio Manager.
- **Structured output, deterministic parsing** (`schemas.py`, `agents/roles.py`): agents
  emit typed objects; the final rating is parsed deterministically — no second LLM call.

## Layer 2 — Memory (from FinMem)
- **Layered store** (`memory/memory_db.py`): short / mid / long / reflection with
  different importance priors.
- **Retrieval ranking** = `similarity + recency + importance/100`.
- **Exponential decay** (`memory/decay.py`): `recency = exp(-Δ/factor)`, `importance *= 0.988`
  — old patterns fade unless reinforced by reuse.
- **Reflection** (`memory/reflection.py`): each realized trade writes a durable lesson.

## Layer 3 — Discipline (from agent-backtest-lab)
- **Net-of-cost is non-negotiable** (`discipline/costs.py`): every P&L subtracts
  turnover cost (bps/side).
- **Leakage firewall** (`discipline/firewall.py`): at time T the agent sees only data ≤ T.
- **Baselines to beat** (`discipline/baselines.py`): buy&hold, momentum, mean-reversion,
  random — net of cost.
- **Overfit / reward-hacking detection** (`discipline/overfit.py`): flags IS→OOS Sharpe
  collapse and drawdown shifts.

## Design rules
1. **Same code path for backtest and live** — `backtest/engine.py` calls the same
   `DecisionGraph.run` as `runner.py`. No separate strategy to drift out of sync.
2. **Provider/broker/LLM are all swappable** behind interfaces — you can change data
   vendor, exchange, or model without touching decision logic.
3. **The cap matters more than the model** — sizing (`risk/`) is hard-clamped; most
   blow-ups are sizing failures, not signal failures.

## Extension roadmap
- [ ] Real embeddings for memory (Voyage/OpenAI) behind `LayeredMemory.embed_fn`.
- [ ] Portfolio-level graph (multi-symbol, correlation-aware sizing).
- [ ] Persist memory to a vector DB (Chroma/pgvector) instead of in-process.
- [ ] Wire live LLM prompts in `agents/llm.py::ClaudeLLM` (currently thin).
- [ ] Celery beat scheduler around `runner.TradingBot.decide` (reuse your existing
      task-queue infra).
- [ ] Deflated/Probabilistic Sharpe + PBO in `discipline/overfit.py`.
- [ ] ccxt idempotency + order reconciliation before enabling live orders.
```
