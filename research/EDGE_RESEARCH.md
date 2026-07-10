# Edge Research — verified findings (deep-research, 25 sources, all claims 3-vote verified)

> 25 claims extracted → 25 confirmed, 0 refuted. Sources: BIS, CMU, López de Prado,
> Journal of Finance, JFE, arXiv, Deribit. Full run: 108 agents, 520 web lookups.

## The #1 finding
**The highest-leverage improvement is validation discipline, not a new signal.**
Standard k-fold CV / hold-out are *invalid* on financial data; in-sample Sharpe
overstates out-of-sample by **2–4×**; overfit "profitable" strategies can be
manufactured from **pure noise** in a few hundred iterations. → We built the Stage 4
gauntlet (PBO, DSR, cost-stress, plateau, falsification) as a direct response.

## Edge families (verified)
| Edge | Real cash flow? | Realistic net | Notes |
|---|---|---|---|
| **Crypto carry / basis** | ✅ funding + basis | low single-digit %/yr | Basis avg ~7%/yr (2019–24); the "Sharpe 7–11" figures are **gross, in-sample, high-leverage-era** and decaying. Our own 0.76%/yr is the right magnitude. |
| **Time-series momentum (TSMOM)** | ❌ prediction | often ~0 net of costs | Real support in crypto; gross often insignificant after costs. Register + test with brutal costs. |
| Cross-sectional momentum | ❌ | weak | Skip. |
| Liquidation-MR, cross-exch arb, pairs, on-chain, options-VRP, seasonality | — | un-adjudicated | No surviving verified claims — research separately, not proven/refuted. |

## Techniques that genuinely move the needle
- **Purged/embargoed CV + CPCV** (k-fold is invalid on serially-dependent data)
- **Deflated Sharpe + PBO** (correct for multiple testing; PBO>0.5 = selection is worse than useless)
- **Falsification audit** (run the whole workflow on shuffled/null data; residual "edge" = leakage)
- Triple-barrier + meta-labeling = legit *tooling*, **not edge by itself** (adds overfitting surface)
- Fractional Kelly / vol targeting for sizing

## Traps (verified)
- Any impressive backtest **without multiple-testing correction** is presumed spurious.
- **Gross in-sample carry Sharpe** treated as a deliverable edge = classic self-deception.
- Published anomalies lose **~58% post-publication** (~26% overfit + ~32% crowding).

## Our Stage 4 gauntlet result on funding-carry (2y, BTC/ETH/SOL/BNB)
`5/6 checks passed → DEPLOYABLE: False`. Passed PBO, cost-stress (survives 3×),
multi-asset (100% positive), DSR, and falsification — but **failed param_plateau**
(only 50% of threshold configs are positive ⇒ param-sensitive/fragile). Correct
outcome: **do not deploy**; the edge is real but fragile and tiny.

## Key sources
- BIS WP 1087 *Crypto carry*; CMU *Carry Trade in Crypto*
- Bailey & López de Prado, *Deflated Sharpe Ratio* (SSRN 2460551); *Backtest Overfitting* (davidhbailey.com)
- López de Prado, *Advances in Financial ML* (Purged CV, CPCV, PBO, triple-barrier, meta-labeling)
- Han, Kang & Ryu 2024 (SSRN 4675565) — crypto TSMOM vs CSMOM
- McLean & Pontiff 2016 (J. Finance); Jacobs & Müller 2020 (JFE) — factor decay
- Nikolopoulos 2026 (arXiv 2604.15531) — falsification audit / effective-multiplicity
