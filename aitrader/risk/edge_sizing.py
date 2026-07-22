"""Size by MEASURED edge, not by a constant — and refuse to trade a dead signal.

THE DEFECT THIS FIXES. `collector/paper.py` sized every position at a flat
`RISK_FRAC = 0.15`:

    tgt_w = RISK_FRAC if signal == "UP" else -RISK_FRAC if signal == "DOWN" else 0.0

Three things wrong with that, all independent of whether the signal is any good:
  1. CONSTANT SIZE — a 51%-confidence call gets the same capital as a 71% one.
  2. NO AGGREGATE CAP — 8 live signals x 0.15 = 120% of equity. This is the whole
     explanation for the paper bot running 6.3x the volatility of buy & hold.
  3. IT IGNORES ITS OWN TRACK RECORD — measured expectancy is -0.017% per call over
     6,259 forward predictions, and it kept sizing at full weight anyway.

WHY THIS IS NOT CURVE-FITTING, which matters because the request that produced it was
"modify the formula so we hit the goal". Tuning the PREDICTION formula until the backtest
looks good is the trap this repo exists to prevent — our own research found that pure
noise manufactures profitable-looking strategies within a few hundred iterations, and the
registry counts every attempt so the deflated-Sharpe bar rises with each one.

This changes the SIZING formula instead, and it only ever makes the bot MORE conservative
in response to evidence it already collected. It cannot manufacture a result: with
expectancy negative, the honest size is zero, and that is what it returns.

THE PROPERTY THAT MAKES IT WORTH HAVING: it generalises. Today it sizes our directional
signal to 0. If a future signal earns a positive measured expectancy, the same function
sizes it up automatically — no code change, no judgement call, no temptation to override.

Kelly is the principled base (EDGE_RESEARCH.md lists fractional Kelly as one of the few
techniques that genuinely moves the needle), deliberately quartered: full Kelly is optimal
only if your estimated probabilities are exact, and ours are estimated from a finite
sample of a near-coin-flip.
"""
from __future__ import annotations

from dataclasses import dataclass

# Quarter Kelly. Full Kelly assumes p is known exactly; ours is measured, noisy, and
# hovering at 0.5 — the regime where over-betting hurts most.
KELLY_FRACTION = 0.25

# Hard ceilings. Kelly can recommend enormous size when p is estimated slightly above 0.5;
# these exist so a measurement artefact can never become a large position.
MAX_WEIGHT_PER_SYMBOL = 0.15
MAX_GROSS_EXPOSURE = 0.60


@dataclass
class EdgeStats:
    """What we have actually MEASURED about a signal, forward, out of sample."""

    n: int                      # matured predictions scored
    hit_rate: float             # fraction correct
    expectancy: float           # mean return per call, net — the number that decides

    @property
    def is_significant(self) -> bool:
        """Is the hit rate distinguishable from a coin flip at 95%?

        With n=6,259 and hit_rate=0.493 the CI is [48.1%, 50.5%] — it contains 50%, so
        the answer is no, and it has stayed no as the sample tripled.
        """
        if self.n < 30:
            return False
        se = (0.25 / self.n) ** 0.5
        return abs(self.hit_rate - 0.5) > 1.96 * se


def kelly_weight(stats: EdgeStats, payoff_ratio: float = 1.0) -> float:
    """Quarter-Kelly fraction from MEASURED stats. Zero unless the edge is real.

    Two independent gates, and both must pass:
      * expectancy > 0      — we are actually making money per call
      * is_significant      — the hit rate is distinguishable from a coin flip

    Either failing returns 0.0. That is the point: a signal that has not proven itself
    gets no capital, however confident it sounds.
    """
    if stats.expectancy <= 0:
        return 0.0
    if not stats.is_significant:
        return 0.0

    p = max(0.0, min(1.0, stats.hit_rate))
    b = max(payoff_ratio, 1e-9)
    edge = (p * b - (1 - p)) / b          # classic Kelly for a binary payoff
    if edge <= 0:
        return 0.0
    return min(edge * KELLY_FRACTION, MAX_WEIGHT_PER_SYMBOL)


def scale_to_gross(weights: dict[str, float],
                   max_gross: float = MAX_GROSS_EXPOSURE) -> dict[str, float]:
    """Scale a book down so total absolute exposure respects the cap.

    The missing piece in the old code: per-symbol limits do nothing if you hold twenty
    symbols. 8 x 0.15 = 120% was never intended, it was just never checked.
    """
    gross = sum(abs(w) for w in weights.values())
    if gross <= max_gross or gross <= 0:
        return dict(weights)
    k = max_gross / gross
    return {s: w * k for s, w in weights.items()}


def target_weights(signals: dict[str, str], stats: EdgeStats,
                   max_gross: float = MAX_GROSS_EXPOSURE) -> dict[str, float]:
    """signals {symbol: UP|DOWN|FLAT} + measured stats -> target weights.

    Returns all-zero when the signal has no proven edge. Today that is exactly what
    happens, and it is the correct answer rather than a failure.
    """
    w = kelly_weight(stats)
    if w <= 0:
        return {s: 0.0 for s in signals}
    raw = {s: (w if sig == "UP" else -w if sig == "DOWN" else 0.0)
           for s, sig in signals.items()}
    return scale_to_gross(raw, max_gross)


def explain(stats: EdgeStats) -> str:
    """One line stating why the book is sized the way it is."""
    w = kelly_weight(stats)
    if stats.expectancy <= 0:
        return (f"size 0: measured expectancy {stats.expectancy:+.4%}/call over "
                f"{stats.n:,} forward predictions is NOT positive")
    if not stats.is_significant:
        se = (0.25 / max(stats.n, 1)) ** 0.5
        return (f"size 0: hit rate {stats.hit_rate:.1%} is not distinguishable from a "
                f"coin flip (95% CI [{stats.hit_rate - 1.96*se:.1%}, "
                f"{stats.hit_rate + 1.96*se:.1%}] contains 50%)")
    return (f"size {w:.1%}/symbol: quarter-Kelly on a measured hit rate of "
            f"{stats.hit_rate:.1%}, expectancy {stats.expectancy:+.4%}, n={stats.n:,}")
