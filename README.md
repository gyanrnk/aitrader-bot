# aitrader — AI Trading Bot

A debate-driven, memory-backed, **discipline-gated** AI trading architecture.
Runs end-to-end with **no API keys** in mock/paper mode; flip a flag to go live.

Distilled from three open-source references (see `ARCHITECTURE.md`):
- **TradingAgents** → multi-agent decision graph
- **FinMem** → layered memory with decay + reflection
- **agent-backtest-lab** → the anti-overfitting / net-of-cost discipline gate

## Quick start
```bash
pip install -r requirements.txt          # only numpy+pandas needed for mock mode

python tests/test_smoke.py               # verify everything runs
python scripts/decide_once.py MOCKX      # one decision + full reasoning trail
python scripts/backtest.py MOCKX         # walk-forward backtest + discipline scorecard
```

## Cost: free by default
The bot trades on a **free deterministic engine** (`QuantEngine`) — no LLM on the
per-bar loop, no API bill. The LLM is **optional** and reserved for the slow loop
(regime/news/reflection). Backends: `quant` (free, default), `groq` (free tier),
`claude` (paid). See **`ECONOMICS.md`** — read it before risking money.

## Going live (staged, in this order — do not skip)
1. `AITRADER_DATA_PROVIDER=yfinance` — real market data, still paper, still free.
2. **Backtest must beat buy&hold NET of cost with no critical overfit flags.** If not,
   stop and fix the signal — don't trade.
3. *(Optional)* `AITRADER_LLM_BACKEND=groq` + `GROQ_API_KEY=...` — free-tier LLM for the
   slow loop only (leave `AITRADER_USE_LLM_IN_DECISION=0`).
4. Paper-trade forward; confirm live tracks the backtest.
5. `AITRADER_BROKER=ccxt` + `AITRADER_ALLOW_LIVE_ORDERS=yes` — **real money. Only after**
   steps 2–4 AND `execution/ccxt_broker.py` has idempotency + reconciliation.

See `.env.example` for every knob.

## Layout
```
aitrader/
  config.py           # one settings object, env-driven
  state.py schemas.py # typed objects passed between agents
  data/               # provider interface + mock/yfinance + indicators
  memory/             # layered memory, exponential decay, reflection
  agents/             # llm client (mock/Claude) + analyst/researcher/trader/risk roles
  orchestration/      # bounded-debate routing + the decision graph
  risk/               # position sizing with hard caps
  execution/          # broker interface + paper/ccxt
  discipline/         # costs, leakage firewall, baselines, overfit checks
  backtest/           # walk-forward engine (same code path as live)
  runner.py           # ties it together for one live cycle
scripts/  tests/
```

## Safety
- Paper broker is the default; live orders are **double-gated** by env flag.
- Every reported P&L is **net of costs** (`discipline/costs.py`).
- Backtests enforce **point-in-time** data (`discipline/firewall.py`) — no lookahead.
- Nothing here is financial advice; validate before risking capital.
