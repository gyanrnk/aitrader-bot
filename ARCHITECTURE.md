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
      **☠️ The trap that makes the naive version wrong** (researched 2026-07-18): on
      **Binance, OKX and Kraken the client-order-ID uniqueness check is scoped to
      OPEN/PENDING orders only**. Binance spot, verbatim: *"Orders with the same
      `newClientOrderID` can be accepted only when the previous one is filled."* OKX:
      *"clOrdId uniqueness check is only applied towards all pending orders."* So in the
      exact failure we are defending against — submit → fills → response times out →
      retry same ID — the exchange happily creates a **second order**.
      **A client order ID is not an idempotency key on those venues; it is a lookup
      handle. Query-before-retry is mandatory, never blind-retry.** (Bybit is the only
      one documenting unconditional `orderLinkId` uniqueness; Hyperliquid's `cloid`
      uniqueness is UNVERIFIED — probe on testnet before relying on it.)
      Query field names: Binance `origClientOrderId`, Bybit `orderLinkId`, OKX `clOrdId`,
      Kraken `cl_ord_id` (NOT `userref` — that is documented as *non-unique*).
      Patterns worth copying, in value-per-hour order:
      1. **Fill dedup by exchange `trade_id`** (Hummingbot `order_fills: Dict[trade_id,
         TradeUpdate]`) — makes fill application idempotent under WS/REST duplication.
         Smallest change, biggest correctness win.
      2. **Client-order-ID formula** — `prefix + side + pair + hex(nonce) +
         md5(uname+pid+ppid)`, so two processes can never collide. **Persist it BEFORE
         the HTTP call, not after.**
      3. **In-flight resolution state machine** (nautilus_trader): threshold → re-query →
         retry budget → force a terminal `REJECTED`/`CANCELED`. A timeout must resolve to
         a *decision*, never stay ambiguous.
      4. **Adaptive poll as a websocket safety net** (Hummingbot): if
         `now - last_recv_time > 60s`, drop poll interval 120s → 5s. A dropped socket then
         degrades latency instead of corrupting state.
      5. **Inferred-fill delta** (nautilus): when the venue reports more filled than cache,
         back-solve `last_px` so VWAP matches venue `avg_px`. Add the negative-price guard
         the original lacks.
      Reference implementation to copy wholesale: **nautilus_trader** — the only one of the
      major bots that treats reconciliation as a first-class subsystem. Note freqtrade
      **does not use client order IDs at all** (recovery is a time-windowed rescan by pair),
      and ccxt never generates one.
```
