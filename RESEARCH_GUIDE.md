# Research Guide — how to find an idea worth testing

Everything we tested that came from *patterns* (RSI, MACD, trend, ML prediction) failed.
Everything with a *mechanism* (funding carry, cross-exchange spread) was at least real —
it only failed on retail fees. **Conclusion: hunt for MECHANISMS, not patterns.**

---

## 1. The ONE question every idea must answer

> ### "Kaun mujhe paisa de raha hai, aur KYUN?"

If you can't name the person/entity paying you and their reason — it's pattern-matching,
and it will fail. No exceptions. This one filter kills 95% of ideas before wasting time.

| Bad answer | Good answer |
|---|---|
| "RSI 30 pe bounce aata hai" | "Ye fund index se nikalne pe **majboori me** bechega — main usse sasta le sakta hoon" |
| "AI predict karega" | "Main leverage provide kar raha hoon, wo mujhe funding **pay** karta hai" |
| "Chart me pattern hai" | "Ye coin institutions ke liye **bahut chhota** hai, isliye price discovery slow hai" |

---

## 2. The 5 places real edges actually live

**A. Forced flows** — someone MUST trade, regardless of price
- Index rebalancing (funds must buy/sell on announcement day)
- Liquidations / margin calls (forced sells into a falling market)
- Fund redemptions, tax-loss selling (year-end), F&O expiry unwinds
- *Mechanism:* they're price-insensitive; you provide the other side.

**B. You provide a SERVICE and get paid** — a real cash flow
- Liquidity (market making) → earn the spread
- Insurance (selling options) → earn the premium
- Leverage (perp funding) → longs pay you
- *Mechanism:* it's a fee for a service, not a bet.

**C. Structural constraints** — big players CAN'T play
- Too small (institutions need size; a ₹50cr opportunity is invisible to them)
- Regulatory (they can't touch certain assets/venues)
- Mandate (a fund literally isn't allowed to hold it)
- *Mechanism:* less competition = less crowded.

**D. Your own information edge** — you know something specific
- Deep domain knowledge others lack (your industry, a protocol, a company)
- *Mechanism:* you're genuinely better informed in a narrow niche.

**E. Predictable behaviour** — reliable human/system patterns
- Time-of-day / expiry-day flows, settlement mechanics
- *Mechanism:* the pattern comes from plumbing, not psychology-guessing.

---

## 3. Red flags — reject BEFORE testing (saves weeks)

- ❌ No mechanism, just a chart pattern
- ❌ "Dekho is chart pe kaam karta hai" (cherry-picked — we PROVED best-strategy differs per asset)
- ❌ Backtest without costs
- ❌ Needs you to predict direction
- ❌ Everyone knows it (RSI/MACD/supertrend/EMA...) → crowded → dead
- ❌ **Someone is selling it to you** (if it worked, why sell?)

## 4. Green flags — bring me this

- ✅ Clear mechanism: you can name who pays and why
- ✅ Niche / small / boring (institutions ignore it)
- ✅ It's a cash flow or a forced flow, not a prediction
- ✅ Nobody's selling a course on it
- ✅ You have specific access or knowledge

---

## 5. Where to actually research (real sources, not gurus)

| Source | What for |
|---|---|
| **SSRN / arXiv q-fin** | Search "anomaly", "market microstructure", "index rebalancing", "limits to arbitrage" |
| **Exchange docs** | Funding mechanics, liquidation engine, settlement rules — the *plumbing* is where mechanisms hide |
| **NSE/BSE circulars** | Index rebalance dates, F&O expiry rules, listing mechanics |
| **Protocol docs** (crypto) | How a DeFi protocol actually pays yield, and who pays it |
| **Quantocracy / quant blogs** | Practitioner writeups with real cost accounting |
| ❌ YouTube / Telegram / courses | Marketing funnels — skip |

---

## 6. The template — send me this and I'll test it same day

```
IDEA NAME:

MECHANISM (who pays me and why?):

RULE:
  - Instrument/market:
  - Entry condition:
  - Exit condition:
  - Position size/direction:

DATA NEEDED (what feed?):

EXPECTED:
  - How often does it trigger?
  - How much per trade (rough %)?
  - How long is each position held?

WHY ISN'T IT CROWDED? (who can't/won't do this?)
```

Even a rough version is fine — I'll formalize it.

---

## 7. What I do with it (same day)

1. Implement it in the aitrader framework
2. Backtest: real data, multi-asset, 3+ years, **net of costs**
3. Gauntlet: PBO · Deflated Sharpe · cost-stress (2x/3x) · param-plateau · multi-asset · falsification (shuffled data)
4. **Honest verdict** — real edge or noise
5. If it passes → live paper forward-test (weeks) → then execution wiring (double-gated)

**The bar:** beats buy & hold net-of-cost, survives multiple-testing, and works across
assets — not just the one you found it on.
