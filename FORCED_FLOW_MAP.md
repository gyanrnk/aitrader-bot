# Forced Flow Map — exchange rules that FORCE someone to trade

> Companion to `RESEARCH_GUIDE.md`. That doc says *hunt mechanisms, not patterns*.
> This doc is the **catalog of mechanisms**, extracted from official exchange rulebooks
> (Kraken Futures / Bybit / OKX) and verified against **live public APIs on 2026-07-17**.
>
> Every row answers: **WHO is forced · WHEN · price-insensitive? · can we SEE it for free?**

---

## 0. The distinction that kills half of all "edge" ideas

Three different things get sloppily called "forced". Only one is real:

| Type | Meaning | Tradeable? |
|---|---|---|
| **FORCED-SETTLE** | Exchange closes you at a price you don't choose | ✅ Genuinely price-insensitive |
| **FORCED-REDUCE** | Shrink by a deadline or be liquidated | ✅ Price-insensitive *at the deadline* |
| **BLOCKED** | Can't *add*, but keep what you have | ❌ **Not a forced flow at all** |

Most "position limit" ideas are only BLOCKED. They die here, before any code.

**And the deepest correction:** *funding rules do not force anyone to trade.* They change the
price at which trading is rational. The **only** genuinely forced, price-insensitive actor in
this entire map is the **liquidation engine** — plus the **exchange's own rule-following**,
which is deterministic and public.

---

## 1. TIER 1 — forced · price-insensitive · **backtestable TODAY**

### 1.1 ★★★ Kraken liquidation executions — free, order-level, history to **2022**

**This is the biggest find in the map.** We have been collecting 10-min snapshots for 6 days
waiting for data. A **4.3-year order-level liquidation dataset** has been sitting on a free
unauthenticated endpoint the whole time.

```
GET https://futures.kraken.com/api/history/v3/market/{symbol}/executions
    ?since=&before=&sort=&count=&continuation_token=
# OpenAPI declares: security: - {}     ← NO AUTH
# Verified: oldest PF_XBTUSD execution = 2022-03-23T10:03:53Z
```

Per liquidation you get: side, size, **the protective limit price (the band)**, fill price,
**mark price at that instant**, and the resting maker it hit.

```json
"takerOrder": { "direction":"Sell", "quantity":"170",
                "limitPrice":"0.070525", "orderType":"PartialLiquidation",
                "reduceOnly":true },
"price":"0.071154", "markPrice":"0.07114969213", "limitFilled":false
```

- **WHO is forced:** the margin-breached trader. Kraken states plainly:
  *"Kraken Derivatives does not offer margin calls or any warnings."* No grace period.
- **Price-insensitive:** **YES — but bounded.** The IOC `limitPrice` caps how far it pushes.
  This is a gentler, more modellable shape than a pure market order.
- ⚠️ **Trap:** the documented `orderType` enum omits **`PartialLiquidation`** — which is what
  live data actually returns. Filter on the documented enum and you **silently drop the most
  common liquidation type.** Match substring `liquidat`, case-insensitive.

**✅ Independently re-verified 2026-07-17 (not taken on trust):**
- No-auth request succeeds; oldest PF_XBTUSD record `1648029833450` = **2022-03-23T10:03:53Z**
- `PartialLiquidation` reproduced live on PF_DOGEUSD (**15 in last 1000 execs, 3.6h**), with the
  full field set: `('PartialLiquidation','Sell','170', limit 0.070525, fill 0.071154, mark 0.07114969213)`
- **Enum trap confirmed, and it's worse than documented:** live types include **both**
  `PartialLiquidation` *and* `FillOrKill` — **neither is in the documented enum.**

> ⚠️ **Honest caveat on sparsity.** Liquidations are **rare and heavily clustered**. In my probe:
> DOGE **15/1000** (1.5%); **SOL, XRP, ETH, BTC: 0/1000 each.** The 4.3-year history is real, but
> building a usable dataset is a **pagination job across symbols and time**, not one call. Budget
> for that. It is still vastly better than waiting weeks for our own snapshots to accumulate.
- Docs: [executions endpoint](https://docs.kraken.com/api-reference/market-history/get-public-execution-events) ·
  [Equity Protection Process](https://support.kraken.com/hc/en-us/articles/360022835671-Equity-Protection-Process)

**Kraken EPP ladder** (`PF_*`): partial liq in **10% increments** → full liq IOC at ≈zero-equity
price → **assignment to registered LPs** → covered liq (5% from best bid/ask) → unwind.
Maintenance margin is fully public via `/derivatives/api/v3/instruments` → `marginLevels`
(PF_XBTUSD: MM 0.5% at tier 1 → 25% at $150M+; **MM = IM/2 at every tier**).

### 1.2 ★★★ Kraken Position Assignment System — *documented program to get PAID for absorbing forced flow*

Kraken has **no insurance fund**. Instead it runs an **opt-in** program where you volunteer to
be the counterparty to liquidations:

> *"The sum total capacity of liquidity providers participating in the program is a de facto insurance fund."*

- LPs set max single-assignment size / max post-assignment position.
- Assignments **split equally** among active LPs, spilling to higher limits.
- Compensation: liquidity pool tops fills into a **0.75%–2.5% profitable window vs mark**.
- ⚠️ **Doc contradicts itself on the floor:** overview says 0.5–2.5%, its own worked example
  says 1%, EPP page says 0.75–2.5%. **Three numbers, three pages → floor is UNVERIFIED.**
- 🚨 **This is not free money.** You are volunteering to inherit positions from traders who
  just blew up, in exactly the conditions where that is most dangerous. The 0.75–2.5% window
  is *compensation for real tail risk*. Resolve the floor with Kraken support before sizing.
- Doc: [Position assignment system](https://support.kraken.com/articles/360022631692-position-assignment-system-derivatives)

### 1.3 ★★ Delisting auto-settlement — the purest forced flow that exists

| | Settlement price | Window | Notice (observed) |
|---|---|---|---|
| **Bybit** | avg **index** price before delisting | **30 min** | **~2 days** (ESUSDT: Jul 8 → Jul 10 2026) |
| **OKX** | avg index price before delisting | **60 min**, 200ms sampling | 7d promised, **6d observed** |
| **Kraken** | VWAP/TWAP + "deviation safeguards", **sole discretion** | 60 min | *"when possible"* — **may be zero** |

Bybit: *"Any open positions … will be automatically closed"*; actions *"final, conclusive, and binding"*;
fixed **0.05%** settlement fee.

- **WHO:** every open position holder + any arb whose hedge leg is on the delisting venue.
- **Price-insensitive:** **maximally.** No opt-out, no price at which they can decline.
- ⚠️ **OKX uses 60 min for delisting but 30 min for scheduled expiry.** Same venue, two windows.
- 🔴 **BUT — see §4.1. The mechanism is certain; the price response is UNVERIFIED folklore.**

**Bybit's auto-delist trigger is computable from free data:**
- Warn at last price ≤ **50 × tickSize** · Delist right at last price < **20 × tickSize**
- `tickSize` from `instruments-info`, last price from tickers → **live "delisting-eligible" screen**
- Caveat: grants a *right*, not an obligation → predicts **eligibility, not timing**
- Doc: [DDM](https://www.bybit.com/en/help-center/article/Bybit-Derivatives-Delisting-Mechanism-DDM)

### 1.4 ★★ Scheduled expiry settlement — deterministic, known years ahead

All three settle at **08:00 UTC** on a **30-minute index average** (Bybit, OKX).
Monthly = last Friday; quarterly = last Friday of Mar/Jun/Sep/Dec.

> ❌ **CORRECTED FOLKLORE:** "quarterly settlement is last-hour TWAP" is **FALSE** for scheduled
> expiry on Bybit and OKX — it is **30 minutes**. The 60-min figure belongs to *delisting* and
> *OKX BTC daily settlement*. Using the wrong window breaks any convergence model.

### 1.5 ★★ Bybit risk-limit adjustment — 17 days notice, exact deadline, in the API

Live verified (announced Jul 7 2026, 32 symbols incl. BLURUSDT, FARTCOINUSDT, XMRUSDT):

- Reduce-only buffer: **Jul 8 07:30 UTC → Jul 25 07:30 UTC** (17 days)
- During: *"only be allowed to reduce your affected position"*
- At end: *"the system will automatically apply the new risk parameters… may be exposed to liquidation risk"*
- **WHO:** holders above the new tier threshold. **Price-insensitive: yes at the deadline.**
- **Cleanest entry in the map:** named symbols + exact UTC deadline + ~17 days notice + free API.

---

## 2. TIER 2 — free public **regime flags** nobody polls (diff-based, start snapshotting NOW)

### 2.1 ★★★ Funding interval escalation — a free 8× carry flag

**OKX** (rule effective Apr 14 2026): rate hits cap at settlement → interval escalates
**8h → 4h → 2h → 1h**, one level at a time. **Bybit**: jumps straight to **1h**.

Why it's economically enormous — OKX with sustained premium P, 0.375% cap:

| Interval | Daily carry |
|---|---|
| N=8h | `min(P, 0.375%)` per 8h → max **1.125%/day (capped, NOT clearing)** |
| N=1h | `min(P/8, 0.375%)` per 1h → **`min(3P, 9%)`/day** |

At P=1%: **1.125%/day vs 3%/day — escalation un-clamps funding and restores up to 8× carry.**
(The `8/N` divisor lands *before* the clamp, so at N=1 the cap barely binds.)

**When the cap binds, funding stops clearing the basis** — the paying side is subsidized, so the
premium has no reason to close. **The cap is why a rich basis stays rich.**

- **Observable, free, real-time:** `nextFundingTime − fundingTime` (OKX) · `fundingInterval` (Bybit)
- **Asymmetry:** escalation is a *published deterministic rule*. **De-escalation is discretionary**
  — *"without further notice"*, no threshold, no timeframe. **Do not assume symmetry.**
- **Live right now:** Bybit has 2 symbols on 1h (B3USDT, HOMEUSDT) — the mechanism is firing today.

> **The funding interval field is a free, public, real-time regime flag that most participants never poll.**

### 2.2 ★★ Bybit announcements API — free, machine-readable, 447 delisting records

```
GET https://api.bybit.com/v5/announcements/index?locale=en-US&type=delistings&limit=5
# verified live, no auth, total: 447
```
Fields: `title, description, type.key, tags, url, dateTimestamp, startDateTimestamp, endDateTimestamp`.
Risk-limit adjustments (§1.5) ride the same feed under a different `type`.

**OKX and Kraken have no equivalent public announcement API** — HTML scraping only.

### 2.3 ★ OKX index-components — only venue exposing live constituents + weights

```
GET https://www.okx.com/api/v5/market/index-components?index=BTC-USDT
```
Returns per-constituent `exch`, `symPx`, `wgt`, `cnvPx`. Note `cnvPx`: the Coinbase BTC/USD leg is
FX-converted to USDT — **the USD/USDT conversion is itself an index input.**

- Constituent swaps often ship with **ZERO notice** (DOG-USDT: announced *and effective* same day).
  → **the endpoint diff beats the announcement page as a signal.**
- **Bybit index composition is NOT in the public API** — JS-rendered page only. **Biggest data gap.**
- **OKX does not name its constituents in any doc** — but the *API* returns them. Docs ≠ API.

### 2.4 ★ Bybit USDC session settlement → ADL rank reset every 8h (novel)

At each 00/08/16 UTC boundary, USDC perps realize unrealized PnL and **reset average entry price**
to the mark. Bybit's **ADL ranking is by leveraged return** — which is a function of entry price.

> **∴ a profitable USDC perp holder's ADL rank is mechanically reset to ~zero every 8 hours.**
> Who sits at the top of the ADL queue is a deterministic function of time-since-session-settlement.

Researcher note: *"I have not seen this discussed anywhere."* Clock is public; the queue is private.

---

## 3. THE ASYMMETRY — Kraken vs Bybit/OKX funding

This is the sharpest structural fact found, and it **directly concerns our active bet**.

| | **Kraken** | Bybit | OKX |
|---|---|---|---|
| Accrual | **Continuous (per-ms)** | Discrete snapshot | Discrete snapshot |
| Settlement | Hourly + on position change | 00/08/16 UTC | 00/08/16 UTC |
| **Rate known in advance?** | ✅ **YES — a full hour** | ❌ updates every minute | ❌ **removed on purpose, 2024** |
| Dodgeable? | ❌ **structurally impossible** | ✅ (±5s uncertainty) | ✅ |
| Pro-rata by time held | ✅ (*"$1.233 per minute"*) | ❌ all-or-nothing | ❌ all-or-nothing |
| Interest component | **None — pure premium** | 0.03%/(24/interval) | 0.01% fixed |
| Cap (majors, live API) | ±0.5%/**hr** | ±0.5%/8h | ±0.375%/8h |
| Cap → escalation | **N/A by design** | → 1h immediately | 8h→4h→2h→1h |

**Kraken:** *"Funding Rate set at the end of the prior Funding Period"* — the 12:00–13:00 rate was
fixed at 12:00 using 11:00–12:00 data. **You know your carry before you take it.**

**OKX deliberately removed this.** It used to run *cross-period collection* (rate known a period
ahead); it migrated to *current-period* through 2024. **Live API proves it: all 509 OKX swaps
return `method: "current_period"` and `nextFundingRate` is empty on 509/509.**

> **∴ The "predictable window where you know what you'll pay" exists ONLY on Kraken.**
> Any strategy premised on a locked-in forward funding rate on Bybit/OKX is built on a mechanic
> those venues specifically engineered away.

### ⚠️ What this means for `data/xfunding.csv` (our active bet) — honest catch

Our spread is `Kraken − OKX`, both annualized. Dimensionally correct. **But we are subtracting
two different objects:**

- **Kraken leg** = a **locked-in forward** rate for the next hour. Final. Knowable.
- **OKX leg** = a **still-updating estimate** for a settlement up to 8h away. Not final.
  (`nextFundingRate` empty on 509/509 → we *cannot* read the forward rate; there isn't one.)

So `spread_pct` mixes a settled number with a live estimate. The arb may still be real — but the
**measurement carries noise we have not accounted for**, and it is not the spread we'd actually capture.

**Plus:** Bybit is **0.4% present (4/1036 rows)** — geo-blocked on GitHub runners. Our
"cross-**exchange**" monitor is really **Kraken-vs-OKX only**. The `bybit` column is decoration.

---

## 4. TIER 3 — mechanism real, but WEAKER than it looks

### 4.1 Delisting price response — mechanism certain, **price behaviour is folklore**

The forced settlement is documented and certain. But: **no rigorous evidence specific to *perp*
delisting announcements exists in the literature.** What exists covers **spot listings/delistings
and regulatory events** — different objects.

- Yang, *Predictive & Explainable Models for Crypto Delistings (Binance)*, APJFS —
  [link](https://onlinelibrary.wiley.com/doi/10.1111/ajfs.70045) — **predicts delistings; does not measure returns**
- Saggu, Ante & Kopiec 2024 — [arXiv](https://arxiv.org/pdf/2412.02452) — spot/regulatory, not perp

> **Keep these separate:** "forced settlement happens" (documented) ≠ "price moves predictably"
> (unestablished). Merging them is exactly the pattern-matching this repo exists to prevent.

### 4.2 Funding dodge — **elective, not forced** (correcting our own proposal)

Both Bybit and OKX document the rule outright:
> Bybit: *"If a position is fully closed before the funding time, no funding fee will be charged or received."*
> OKX: *"If you close your position before the funding fee assessment, you're exempt."*

Bybit even documents a **±5s zone of non-determinism** — the dodge is real but has a hard
execution boundary.

**But it is NOT forced flow, and we should not have called it that:**

- Nobody is *forced* to dodge — it's **elective**.
- Dodgers are **price-sensitive by construction**: only rational when round-trip cost
  (2× taker + spread + slippage) < funding owed. At typical 0.01% funding it is **deeply
  unprofitable**. → **the dodge population is a step function of the funding rate, not a constant.**
- It is **round-trip and self-reversing** (sell-then-buy) → **mean-reverting, not directional**.
- It is **self-limiting**: mass dodging moves the premium → changes the rate → removes the reason.

The real object is *"a predictable, funding-magnitude-gated, mean-reverting liquidity-demand spike
bracketing a known timestamp — on discrete venues only."* Much narrower than "forced flow".
**No official source quantifies it. Measure before building.**

### 4.3 Inverse/coin-margined "forced rehedging" — **overstated**

Convexity (payoff ∝ 1/P) is real math. But it appears in **no exchange rule** — neither Kraken's
inverse spec nor Bybit's inverse docs mention convexity or delta drift at all. **Rehedging is
elective; thresholds are private.** Does not belong in this map at the same level as §1.

The genuinely structural coin-margined fact: **Kraken caps *retail* inverse leverage at 2×**
(`retailMarginLevels` IM 50% / MM 25% vs professional 2%/1% = 50×).

---

## 5. ☠️ KILLED — with evidence

### 5.1 "OI drop + price spike ≈ liquidation cascade" — **empirically dead at our granularity**

Tested directly: 25,000 consecutive PF_XBTUSD executions (7.31h) vs **our own
`data/market/*.csv`** OI-change distribution (589 samples, same Kraken endpoint → apples-to-apples).

| | Result |
|---|---|
| Liquidations | **0.99% of notional volume** (745/25,000 executions) |
| Clustering | only **9 of 45** 10-min buckets had *any* liquidation |
| Biggest bucket | $376,237 = 17.3% of bucket volume — but only **0.294% of OI** |
| Our OI noise | median 0.166% · p90 **0.942%** · p99 **2.395%** · max **6.327%** |

> **33% (193/589) of our ordinary 10-min OI moves are LARGER than the single biggest liquidation
> bucket in 7.3 hours.** Best-case S/N ≈ 1.8:1.

Confounders, all indistinguishable in a 10-min OI delta: voluntary closes (97% of executions),
**netting** (the sampled liq hit a `reduceOnly` maker → OI dropped **2×** the liq size, so the
mapping isn't even a fixed constant), expiry, MM inventory cycling, funding-clustering, aliasing.

**→ Delete the proxy. Take the real data (§1.1).** Same host we already poll.

### 5.2 Corrected folklore — three claims that are simply wrong

| Claim | Reality |
|---|---|
| "OKX has a REST liquidation endpoint (last 7 days)" | **Does not exist.** Grepped the full 5.1MB docs page: **zero** hits. CCXT-era stale folklore. WS only, and **explicitly sampled**: *"This data doesn't represent the total number of liquidations on OKX."* |
| "Kraken has no public liquidation data" | **False** — §1.1, free, order-level, → 2022 |
| "Bybit liquidation history is usable pre-Feb-2025" | **Systematically undercounted.** Old `liquidation.{symbol}` topic was throttled to **1 msg/symbol/sec** — silently undercounting *worst during cascades*. `allLiquidation` (500ms, "all") added 2025-02-20; old topic's doc page is now **404**. Most 3rd-party Bybit liq history is biased. |

### 5.3 "Position caps force large holders to unwind" — **FALSE for OKX** (BLOCKED, not FORCED)

OKX OI limits are dynamic/per-user, but: *"Reduce-only orders are not restricted by this rule"*,
new opens rejected with error **54030**, **existing positions are not liquidated**. Falling platform
OI shrinks your limit but **does not force you out**. This is BLOCKED — §0.

---

## 6. Free, no-auth endpoints — the data we actually have access to

| Purpose | Endpoint | History? |
|---|---|---|
| ★ **Kraken liquidations** | `futures.kraken.com/api/history/v3/market/{sym}/executions` | ✅ **→ 2022** |
| Kraken margin tiers | `futures.kraken.com/derivatives/api/v3/instruments` → `marginLevels` | live |
| Kraken index constituents | [support article](https://support.kraken.com/articles/9551424898964-index-constituents-derivatives) (14 named) | page |
| Bybit announcements | `api.bybit.com/v5/announcements/index?type=delistings` | ✅ 447 records |
| Bybit risk-limit tiers | `api.bybit.com/v5/market/risk-limit` | live |
| Bybit funding interval + caps | `api.bybit.com/v5/market/instruments-info` | live |
| Bybit liquidations | WS `allLiquidation.{sym}` (500ms) | ❌ live only |
| Bybit ADL thresholds | `api.bybit.com/v5/market/adlAlert` + WS | ❌ state only |
| Bybit insurance fund | `api.bybit.com/v5/market/insurance` | live |
| OKX index components | `okx.com/api/v5/market/index-components` | ❌ diff only |
| OKX funding interval | `okx.com/api/v5/public/funding-rate` → `nextFundingTime − fundingTime` | ❌ diff only |
| OKX position tiers | `okx.com/api/v5/public/position-tiers` | live |

> ⚠️ **Diff-based observables have NO history.** Bybit delistings, OKX index-components, OKX funding
> interval — their signal is in the *change between polls*. **A forced-flow map is only as good as
> the date you start snapshotting.** Three Bybit delistings landed during the research session alone
> (2026-07-17 09:07 UTC). Start snapshotting before modelling.

---

## 7. API traps — read the API, not the docs

| Trap | Doc says | Live API says |
|---|---|---|
| **Bybit funding cap (BTCUSDT)** | formula → **0.375%** | **0.5%** — 33% off. *Never compute it; read `upperFundingRate`.* |
| **"Bybit = 8h"** | help center implies 8h norm | **4h: 412 · 8h: 287 · 1h: 2** — **false for 59% of the book** |
| **Kraken liq `orderType`** | enum omits it | returns **`PartialLiquidation`** — filter on enum → **silently drop most liquidations** |
| **Kraken `maxPositionSize`** | doc example 1,000,000 | **75,000,000** — doc stale |
| **Bybit ADL thresholds** | *"a constant set by Bybit"* | **not constants** — per-pool: 463 syms at −0.3, **279 at −1**. BTCUSDT is in the **−1** bucket → PnL-drawdown ADL effectively **unreachable**; only `balance ≤ 0` path is live. Symbols with balance ≤ 0 right now: **0**. |
| **Kraken delisted symbols** | — | **vanish from the list** (323 instruments, **0** with `tradeable:false`) → observable is *diffing the symbol set*, not a status field |

---

## 8. Ranked shortlist for THIS project

| # | Mechanism | Forced? | Price-insens.? | Free data? | **History?** |
|---|---|---|---|---|---|
| **1** | **Kraken liquidation provision** (§1.1/§1.2) | ✅ | ✅ bounded | ✅ | ✅ **4.3 yrs** |
| **2** | **Funding-interval escalation flag** (§2.1) | regime | med | ✅ | ❌ snapshot now |
| **3** | **Kraken forward-known funding** (§3) | info edge | — | ✅ | ✅ ours + Kraken |
| **4** | Bybit risk-limit buffer (§1.5) | ✅ REDUCE | ✅ at deadline | ✅ | ❌ snapshot now |
| **5** | Delisting settlement (§1.3) | ✅ SETTLE | ✅ total | ✅ Bybit only | ⚠️ **price response unproven** |
| **6** | Bybit USDC ADL-rank reset (§2.4) | ✅ if ADL'd | ✅ | clock only | ❌ queue private |
| — | ~~OI liquidation proxy~~ | — | — | — | ☠️ **§5.1** |
| — | ~~Funding dodge as forced flow~~ | ❌ elective | ❌ | — | ☠️ **§4.2** |

**#1 is the only row with forced + price-insensitive + free + deep history.** It is the one we can
backtest **today** instead of waiting weeks. That is where the gauntlet should point next.

---

## 9. UNVERIFIED — do not build on these

- **Perp delisting → predictable price response** (§4.1) — literature covers spot/regulatory only
- **Kraken PAS profitability floor** — docs say 0.5% / 1% / 0.75% on three different pages
- **ADL frequency, all three venues** — *structurally unverifiable*; nobody publishes an event log.
  → **We could build this dataset by polling Bybit `adlAlert` — genuine edge in information nobody stores.**
- **OKX index constituents** — not named in any doc (but the **API returns them** — use the API)
- **Kraken index provider** — CF Benchmarks *not* confirmed by Kraken's own docs. KFRI is a separate
  *measurement* product, **not** the contract's index. Do not conflate.
- **Bybit cap formula/API discrepancy** — reason unknown
- **Bybit `allLiquidation` batching** inside a 500ms burst — quiet sample can't answer
- **Bybit BTC/ETH exclusion from dynamic settlement frequency** — sourced only to a PR Newswire
  release, not Bybit docs; live API is *circumstantially* consistent. **Unconfirmed.**
- **Kraken inverse settlement window** — 16:00 London vs 07:30–08:00 UTC inconsistent as fetched
- **Kraken US 8h vs EEA 1h funding split** — search snippet only
- **Tick-size/leverage changes force unwinds** — no doc on any venue supports this. **Folklore.**

---

*This document maps exchange mechanics and data availability. It is not investment advice, and
nothing here is assessed as a trade recommendation — tradeability is an empirical question these
docs cannot settle. That is what `discipline/` is for.*
