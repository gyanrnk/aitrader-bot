"""Delta India funding-carry check — turns delta_funding.csv into a trade/no-trade read.

THE QUESTION THIS ANSWERS. A GO alert fires the instant a hedgeable coin's funding
touches 50%/yr. But one print is not an edge — funding resets every 8h and a single
spike that collapses next settlement is a guaranteed loss (you pay ~0.4% round-trip to
collect ~0.05%). So the real question is not "did it touch 50%?" but "did it STAY rich
long enough to clear cost?" This module reads the recorded funding history and answers
that with numbers instead of eyeballing a CSV.

THE COST ANCHOR (honest, and the reason 50%/yr is the GO bar).
  Delta India delta-neutral round trip ≈ 0.40%: perp taker ~0.05%/side + spot taker
  ~0.05%/side, entry AND exit. Funding pays every 8h (3×/day). At exactly 50%/yr:
      50%/yr ÷ 365 = 0.137%/day ÷ 3 = 0.0457%/settlement
      9 settlements (3 days) × 0.0457% = 0.411% ≈ the 0.40% round-trip cost.
  So 50%/yr sustained for THREE DAYS just breaks even on cost. To actually net positive
  you need funding ABOVE 50%, or a hold LONGER than 3 days, or both. That is exactly what
  the windows below measure: cumulative funding minus the one-time 0.40% round trip.

WHAT IT DOES NOT DO. It does not place a trade, size a position, or clear the gauntlet.
It is step 2 of the pipeline (RECORD -> *does-it-hold* -> napkin R8 -> tiny real trade).
A CANDIDATE verdict means "worth taking to the napkin", never "trade now".
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

# --- cost / mechanism constants (single source of truth; edit here if fees change) ---
ROUND_TRIP_COST_PCT = 0.40        # entry+exit, delta-neutral pair on Delta India
GO_ANNUAL_FUNDING_PCT = 50.0      # the alert bar (kept in sync with delta_india.py)
SETTLEMENTS_PER_DAY = 3           # 8h funding
SETTLE_SECONDS = 8 * 3600
# funding per settlement that annualizes to the GO bar (= the 3-day-hold breakeven rate)
GO_FUNDING_8H = GO_ANNUAL_FUNDING_PCT / (SETTLEMENTS_PER_DAY * 365)   # ≈ 0.0457%/8h

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "delta" / "delta_funding.csv"
DEFAULT_WINDOWS_DAYS = (1, 3, 7, 14, 30)


def load(path: str | Path = DEFAULT_CSV) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _epoch(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def settlements(rows: list[dict], symbol: str) -> list[dict]:
    """Collapse the ~10-min samples to ONE representative point per 8h settlement window.

    The collector samples every ~10 min, but funding is only charged at the 8h boundary.
    We floor each sample's timestamp to its 8h bucket (aligned to 00:00 UTC) and keep the
    LAST sample in each bucket — the value closest to when that settlement actually pays.
    """
    buckets: dict[int, tuple[float, dict]] = {}
    for r in rows:
        if r.get("symbol") != symbol:
            continue
        try:
            t = _epoch(r["ts"])
        except (KeyError, ValueError):
            continue
        b = int(t - (t % SETTLE_SECONDS))
        cur = buckets.get(b)
        if cur is None or t > cur[0]:
            buckets[b] = (t, r)
    out = []
    for b in sorted(buckets):
        r = buckets[b][1]
        try:
            out.append({
                "bucket": b,
                "dt": datetime.fromtimestamp(b, tz=timezone.utc),
                "funding_8h": float(r["funding_pct_8h"]),
                "annual": float(r["annual_funding_pct"]),
                "mark": float(r.get("mark_price") or 0),
            })
        except (KeyError, ValueError):
            continue
    return out


def hottest(rows: list[dict]) -> str | None:
    """Hedgeable symbol with the richest funding at its most recent settlement."""
    best, best_val = None, float("-inf")
    for sym in {r.get("symbol") for r in rows} - {None}:
        setts = settlements(rows, sym)
        if setts and setts[-1]["annual"] > best_val:
            best, best_val = sym, setts[-1]["annual"]
    return best


# A "fat & fast" carry: a short hold (≤7 days) already clears cost AND annualizes richly.
# This is the case the 50%/yr GO bar is designed to catch — worth the operational risk.
RICH_APR = 40.0          # realized APR (%/yr) over a short window to call it "rich"
FAST_MAX_DAYS = 7        # "short hold" horizon
# A "thin & slow" carry: clears cost only after weeks, at a low APR. Real but marginal —
# a month of capital locked and hedge-leg liquidation risk for ~half a percent.
THIN_MIN_DAYS = 14
THIN_MAX_APR = 25.0


def _verdict(windows: list[dict], latest: dict) -> dict:
    """Translate the window table into a trade/no-trade code + plain-words reason.

    The profit condition is net-of-cost, NOT "funding touched the alert bar" — the two
    come apart exactly in the low-but-steady regime, where funding never nears 50%/yr yet
    a long enough hold still clears the one-time 0.40% cost. The codes name that shape:
        FLIP      funding negative — the clean short-perp/buy-spot hedge doesn't apply
        BELOW     no hold horizon clears cost — entering now loses money
        THIN      clears cost only over weeks, at a low APR — real but marginal
        WATCH     clears cost but modest/borderline — not yet worth it
        CANDIDATE a short hold already clears cost AND annualizes richly — take to napkin
    A CANDIDATE goes to the napkin R8 + gauntlet next; it is NEVER a trade instruction.
    """
    go_now = latest["annual"] >= GO_ANNUAL_FUNDING_PCT

    if latest["funding_8h"] < 0:
        return {"code": "FLIP", "go_now": False,
                "msg": "Funding NEGATIVE hai — is direction mein hedge ke liye spot inventory "
                       "chahiye (short perp + buy spot wala clean case nahi). Abhi skip."}

    positive = [w for w in windows if w["net"] > 0]
    if not positive:
        best = max(windows, key=lambda w: w["net"]) if windows else None
        gap = (-best["net"]) if best else None
        return {"code": "BELOW", "go_now": go_now,
                "msg": "Koi bhi hold window round-trip cost (0.40%) clear nahi karta — abhi "
                       "enter karna = loss." + (f" Sabse accha window bhi {gap:.2f}% short hai."
                                                if gap is not None else "")}

    # Fat & fast: a short hold already clears cost at a rich APR — the real green light.
    short_rich = [w for w in positive if w["days"] <= FAST_MAX_DAYS and w["apr"] >= RICH_APR]
    if short_rich:
        soon = min(short_rich, key=lambda w: w["days"])
        return {"code": "CANDIDATE", "go_now": go_now,
                "msg": f"{soon['days']}-din hold pe hi net +{soon['net']:.2f}% "
                       f"(realized {soon['apr']:.0f}%/yr) — fat aur fast. "
                       f"Ab napkin R8 + gauntlet, phir TINY real trade."}

    # Thin & slow: clears cost only over weeks, at a low APR — real but probably not worth it.
    longest = max(positive, key=lambda w: w["days"])
    if longest["days"] >= THIN_MIN_DAYS and longest["apr"] < THIN_MAX_APR:
        per_month = longest["net"] / (longest["days"] / 30.0)
        return {"code": "THIN", "go_now": go_now,
                "msg": f"Cost sirf {longest['days']}-din hold pe clear hota hai "
                       f"(net +{longest['net']:.2f}%, ~{per_month:.2f}%/mahina, "
                       f"{longest['apr']:.0f}%/yr). Bahut patla + mahina-bhar capital + hedge-leg "
                       f"liquidation risk — isiliye hum 50% ka fat spike wait karte hain."}

    return {"code": "WATCH", "go_now": go_now,
            "msg": f"Net positive (+{longest['net']:.2f}% over {longest['days']}d, "
                   f"{longest['apr']:.0f}%/yr) par abhi patla/borderline. Aur richness chahiye."}


def analyze(rows: list[dict], symbol: str,
            windows_days: tuple[int, ...] = DEFAULT_WINDOWS_DAYS,
            now: float | None = None) -> dict:
    """Full carry read for one symbol: per-window economics + a single verdict."""
    setts = settlements(rows, symbol)
    if not setts:
        return {"ok": False, "symbol": symbol, "reason": "is coin ka koi funding data nahi"}
    if now is None:
        now = setts[-1]["bucket"] + SETTLE_SECONDS      # end of the last settlement seen

    windows = []
    for d in windows_days:
        cutoff = now - d * 86400
        w = [s for s in setts if s["bucket"] >= cutoff]
        if not w:
            continue
        cum = sum(s["funding_8h"] for s in w)
        n = len(w)
        windows.append({
            "days": d, "n": n,
            "avg_8h": cum / n,
            "cum": cum,
            "net": cum - ROUND_TRIP_COST_PCT,
            "apr": (cum / n) * SETTLEMENTS_PER_DAY * 365,
            "above": sum(1 for s in w if s["funding_8h"] >= GO_FUNDING_8H),
        })

    latest = setts[-1]
    return {
        "ok": True,
        "symbol": symbol,
        "as_of": latest["dt"].isoformat(),
        "latest_annual": latest["annual"],
        "latest_8h": latest["funding_8h"],
        "n_settlements_total": len(setts),
        "history_days": round((setts[-1]["bucket"] - setts[0]["bucket"]) / 86400, 1),
        "breakeven_cost_pct": ROUND_TRIP_COST_PCT,
        "go_bar_annual": GO_ANNUAL_FUNDING_PCT,
        "windows": windows,
        "verdict": _verdict(windows, latest),
    }
