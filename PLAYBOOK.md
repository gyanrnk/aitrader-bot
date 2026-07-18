# The Playbook — how we decide what to build

> `RESEARCH_GUIDE.md` says *hunt mechanisms, not patterns*.
> `FORCED_FLOW_MAP.md` is the catalog of mechanisms.
> **This doc is the filter** — the arithmetic that decides whether a real mechanism is
> worth building. Enforced in code: `aitrader/research/napkin.py`.

Written 2026-07-18, after 5 tested ideas and 5 rejections.

---

## 1. The finding that reframes everything

Every rejection so far died the same way, and we kept calling it bad luck:

| Idea | Mechanism real? | Edge | Cost | Result |
|---|---|---|---|---|
| `funding_carry` | ✅ | ~0.8%/yr | turnover | ❌ |
| `liq_meanrev` | ✅ 78.4% of fills | **1.34 bps** | **5 bps** | ❌ |
| `xexch_arb` | ✅ | lived 13.8h | needed 163h | ❌ |
| `delist_event` | ❌ not forced flow | — | — | ❌ |
| `tsmom` / ML | ❌ no mechanism | — | — | ❌ |

**Three of five had a genuinely real mechanism and still died on cost.** That is not
variance. Here is why, verified against primary exchange fee schedules (2026-07-18):

| Venue | When does maker fee go NEGATIVE? |
|---|---|
| Kraken Futures | **$250M / 30 days** → −0.003% |
| Binance spot | **Never.** VIP9 ($4B/30d) still charges **+1.1 bps** |
| Bybit | No negative maker tier published at all |

> ### Maker rebates are VOLUME-gated, not SKILL-gated.
> We can never reach market-maker economics. The door is volume, and we will never
> walk through it. So `R3 edge > cost` is **structural**, not a handicap we out-think.

**The honest reframe:** we were playing a game where our cost was ~10× the
counterparty's, and the prizes are sized for *their* cost, not ours. Any edge large
enough to clear *our* 5 bps was harvested long ago by someone paying 0.5 bps.

---

## 2. The napkin test — run this BEFORE building anything

```bash
python scripts/napkin.py --name "..." --mechanism "who pays me and why" \
    --edge 1.34 --cost 5.0 --trades-per-year 1000 --capacity 25 \
    --measured --notional-weighted
```

Six rules. Each one is the post-mortem of a specific dead idea:

| Rule | Kills when | Learned from |
|---|---|---|
| **R0** no mechanism | can't name who pays and why | `tsmom`, ML |
| **R1** settle ≠ trade | no order reaches the book | `delist_event` |
| **R2** zero-net-supply | rule forces BOTH sides → net zero | `delist_event` |
| **R3** edge < 2× cost | the most common death | `liq_meanrev`, `funding_carry` |
| **R4** life < breakeven | opportunity dies before cost amortises | `xexch_arb` |
| **R5** not notional-weighted | statistic isn't trustworthy yet | `liq_meanrev` |
| **R6** capacity | edge real but can't absorb capital | `liq_meanrev` |

**Why 2× and not 1×:** quoted cost is the optimistic case. Spread widens exactly when
you want to trade, slippage grows with size, and a strategy sitting at `edge == cost` is
a coin flip on execution quality alone.

**The filter is back-tested against our own graveyard** (`tests/test_napkin.py`) — it
must kill all 5 dead ideas *for the right reason*, and must NOT kill a control. A filter
that can't reproduce known rejections is worthless; one that kills everything is worse.

**It is mood-proof.** Specify `liq_meanrev` the way a hopeful person would — cherry-pick
+74.87 bps, assume 2 bps cost, headline +728%/yr — and it still returns KILL, caught by
R6 on the $3.71 fill size. Two independent rules cover that trap.

### Realistic round-trip costs (use these, not optimism)

```
crypto perp, majors, maker both sides   ~4 bps    (Bybit VIP0 maker 0.02%/side)
crypto perp, majors, taker out          ~7 bps
crypto perp, midcap/microcap            10-30+ bps (spread dominates, widens on stress)
dying microcap perp                     ~50 bps
```

---

## 3. Where we actually have an advantage

Everything above is bad news. This part is not, and it is the first genuinely
*narrowing* insight we've had.

Thin competition exists where opportunities are **too small for institutions**. But small
also triggers R6 — that is exactly how `liq_meanrev` died (+74 bps on $3.71 fills).

**Except our capital requirement is tiny.** We don't need an opportunity that absorbs
$10M. We need one that absorbs **₹5–10 lakh (~$6–12k)**. An institution cannot be
bothered to model something that caps out at $50k; for us that is the entire book.

> ### The target zone
> **An opportunity that absorbs $10k–100k, but NOT $10M.**
> Big enough that our capital fits. Small enough that a professional never looks.

This is the first time our search space has been *defined* rather than "find an edge".
Note it is also a narrow band — most things are either too small (R6) or already
arbitraged (R3).

---

## 4. The workflow

```
1. Idea arrives (from FORCED_FLOW_MAP §8, or anywhere)
2. Napkin test          -> KILL? stop. Write down WHY. That is the deliverable.
3. Pre-register in research/hypotheses.json BEFORE looking at data
   - state the falsifiable prediction
   - state the bar, in numbers, that cannot be moved later
4. Measure the CHEAPEST decisive quantity first — not a backtest
   (liq_meanrev needed no backtest: mark price rides on every execution)
5. Survives? -> Stage 4 gauntlet (PBO, DSR, cost-stress, plateau, falsification)
6. Survives? -> forward paper trade for weeks
7. Only then, tiny real size
```

**Step 4 is where the leverage is.** Three of our five rejections were settled by a
direct measurement, not a backtest — hours instead of a week.

**Step 3 is not optional.** `xexch_arb` ran as our live bet for two days without ever
being registered. It was registered retroactively, at the moment of its rejection.

---

## 5. Traps that have actually bitten us

| Trap | What happened |
|---|---|
| **Statistic without weighting** | +74.87 bps unweighted → **+1.34 bps** money-weighted |
| **Assumed hold period** | `arb_calc` priced a 30-day hold on a spread that lived 13.8h. `+6.7%/yr` was really **−166%/yr** |
| **Silent sample loss** | Bybit reuses tickers; 6/193 delisting events would have vanished — and those were the coins that did NOT stay dead, biasing results *toward* the strategy |
| **"Forced" ≠ forced** | Cash settlement touches no order book. Both sides settle → net zero |
| **Hardcoded UI numbers** | Dashboard said "tested: 2" when it was 7; said "Carry: 5–10% path" for a rejected idea |
| **Waiting too long** | Planned 2–4 weeks on `xexch_arb`; 2 days sufficed — the event fires 42×/2 days |
| **Local ≠ deployed** | Fixed the mock-data default locally; `yfinance` isn't installed on the cloud, so nothing changed for the user |

---

## 6. Open questions — honestly unresolved

- **Arena.** Everything above is crypto perps — the most arbitraged retail arena there
  is. Cost stacks for India F&O / equities are still being researched. **Not yet decided.**
- **Does the target zone (§3) contain anything real?** Unknown. It is a well-defined
  place to look, not evidence that something is there.
- **Is `R3`'s 2× safety factor right?** Chosen by judgement, not measurement.

**Nothing has passed the napkin test yet.** That is the current, honest state.
