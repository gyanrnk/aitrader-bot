# Economics & the honest truth about profit

Read this before you risk a rupee.

## 1. No bot guarantees profit
Profit = **edge** − **costs** − **mistakes**. The bot only executes; it does not
create edge. If your signal has no real statistical advantage, a more sophisticated
bot just loses money faster and more confidently. This architecture is built to:
- **find out** whether you have edge (honest, net-of-cost, leakage-free backtests),
- **protect capital** while you find out (hard risk caps, paper-first),
- **cost you as little as possible** to run (LLM off the hot path).

That is the most any honest system can promise.

## 2. Why the LLM is OFF the trading loop
LLMs are slow, non-deterministic, and priced per token — three things you do **not**
want in a per-bar trade decision.

| Backend | Cost per decision* | Per-bar? |
|---|---|---|
| `quant` (default) | **₹0** | ✅ yes — this is the brain that trades |
| `groq` (free tier) | ~₹0 (rate-limited) | ❌ slow loop only |
| `claude` | ~₹1–8 per debate | ❌ slow loop only |

\* Order-of-magnitude for a full multi-agent debate. On a small account, paying an LLM
every bar can turn a *winning* strategy into a *losing* one purely on API cost.

**The rule enforced in code** (`orchestration/graph.py`): the per-bar decision uses the
free `QuantEngine` unless you set `AITRADER_USE_LLM_IN_DECISION=1`. The paid/Groq model
is reserved for the **slow loop** — things that happen rarely and add real value:
- daily **regime classification** (trending vs choppy → which strategy to enable),
- **news/earnings** parsing when an event actually fires,
- post-trade **reflection** (writing lessons into memory).

## 3. Costs that actually decide profitability (in order)
1. **Spread + slippage + fees** — modeled in `discipline/costs.py`; every P&L is net.
   Trade less; each round-trip pays 2× the per-side cost.
2. **Taxes** (e.g. STT/brokerage/GST in India, or exchange fees in crypto) — add these
   to `cost_bps_per_side` to stay honest.
3. **Infra** — a VPS is a few hundred ₹/month; data feeds vary.
4. **LLM** — near-zero if you keep it off the hot path (default).

## 4. The only responsible path to going live
```
1. quant backend, mock data      → verify the machine works           (done)
2. quant backend, yfinance data  → backtest on REAL history
3. Does it beat buy&hold NET of cost, with NO critical overfit flags?
     NO  → stop. iterate the signal. do not trade.
     YES → paper-trade forward for weeks. does live match backtest?
4. Only then, tiny real size (risk_per_trade_pct=0.005), one symbol.
5. Scale slowly, only while live results track the backtest.
```
Skipping step 3 is how people lose money. The discipline layer exists to make step 3
impossible to fake.

## 5. Where your edge will actually come from
Not the LLM. Realistically: a **specific, tested inefficiency** — a well-tuned trend/
mean-reversion rule on the right instrument and timeframe, disciplined sizing, and
low costs. The LLM's honest job here is **research and context**, not signal generation.
Tune `agents/llm.py::QuantEngine` and `discipline/` — that is where the money is.
