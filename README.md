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

## Strategies — pluggable, and gated before they run

```bash
python scripts/napkin.py --help                        # kill an idea in 60 seconds
python scripts/strategy_backtest.py BTC-USD 730 5.0    # net-of-cost backtest vs buy & hold
```

Every strategy inherits from `aitrader/strategy/base.py` and **must** implement
`describe()`, returning a napkin `Idea` — who pays me, why, and what barrier stops this
being arbed away. `gate()` runs the napkin test against that self-description, so a
strategy with no mechanism is refused **at definition time**, before it emits a signal.

Two shapes, because the work genuinely has two:

| | For | Produces |
|---|---|---|
| `Strategy` | bar-by-bar (trend, mean-reversion) | `Signal`: action · confidence · **reason** · price · timestamp |
| `MechanismStudy` | event-driven (funding escalation, liquidations) | a measured edge, not a per-bar signal |

`reason` names **which rule fired**. A signal you cannot debug is one you cannot honestly
reject either.

### Sample output — 2 years of BTC-USD, net of 5 bps/side

```
        strategy  total_return  sharpe  max_drawdown  win_rate  n_trades  bars_in_market
 ma_cross_50_200        -0.161  -0.300        -0.203     0.489        48           0.311
rsi_rev_14_30_70         0.014   0.157        -0.040     0.444        35           0.037
      buy & hold        -0.021   0.207        -0.531     0.497         0           1.000
```

Both fail the napkin gate first (**R0** no mechanism, **R7** no barrier) — they are
included precisely so the negative is measured rather than assumed.

**Read the RSI row carefully — it is the trap this repo exists to catch.** It "beats"
buy & hold by +3.5% on total return, which looks like a win. But it is in the market
**3.7% of the time** (27 of 730 bars), its Sharpe is **lower** than buy & hold's, and the
t-stat on its active bars is **+0.24**. It did not outperform; it sat in cash through the
drawdown. Judge on risk-adjusted return and sample size, never on the headline.

MA crossover is the same family as `tsmom`, which scored **3/6** on the Stage-4 gauntlet
(PBO 0.76, DSR 0, falsification p=0.15) and was rejected. A single-config backtest on one
symbol is not evidence — see `PLAYBOOK.md`.

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
