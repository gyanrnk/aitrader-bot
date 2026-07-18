"""Funding-interval escalation episodes — reconstructed from history, not waited for.

THE DATA UNLOCK: I told the user this hypothesis needed WEEKS of live snapshotting,
because `nextFundingTime - fundingTime` is a live-only field with no history. That was
wrong, and wrong the same way the Kraken liquidation call was wrong.

    GET /api/v5/public/funding-rate-history?instId=X&limit=100

returns ~100 past settlements per symbol, each stamped with `fundingTime`. The GAP
between consecutive settlements IS the interval that applied. So escalation history is
fully reconstructable, retroactively, for every symbol at once.

Verified before this file was written: LRC-USDT-SWAP gaps {4h:81, 2h:1, 1h:17} — the
complete documented 4h->2h->1h ladder, recorded in public history.

WHAT WE ARE TESTING (registry: `funding_escalation`, bar pre-registered at 40bps):
OKX escalates when funding hits its cap at settlement. A binding cap means funding has
stopped clearing the basis — the paying side is subsidised, so the premium has no reason
to close. Escalation un-clamps it, and because the 8/N divisor lands BEFORE the clamp,
8h->1h can restore up to 8x the daily carry.

--------------------------------------------------------------------------------------
THE CHECK MOST LIKELY TO KILL IT — TIMING.

Escalation is TRIGGERED BY a settlement whose rate hit the cap. That fat settlement is
already paid by the time the interval visibly shrinks. So we must split the episode:

    trigger  : the capped settlement that CAUSED escalation   <- NOT ours, we're too late
    capture  : every settlement AFTER the interval shrank     <- the only thing we can trade

If the money is concentrated in the trigger, the signal is unlearnable by construction:
by the time you can see it, you have missed it. `capture_bps` is the honest number and
the only one the pre-registered bar applies to.

This is the same failure shape as `delist_event`, where the announcement turned out to
be a LAGGING indicator of a crash that had already happened.
"""
from __future__ import annotations

import json
import urllib.request
from collections import Counter

import numpy as np

HIST = ("https://www.okx.com/api/v5/public/funding-rate-history"
        "?instId={}&limit=100")
ALL_SWAPS = "https://www.okx.com/api/v5/public/funding-rate?instId=ANY"

EPISODE_FIELDS = ["inst_id", "start_ts", "end_ts", "default_h", "min_interval_h",
                  "n_settlements", "duration_h", "trigger_bps", "capture_bps",
                  "total_bps", "direction"]


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "aitrader/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def all_swaps() -> list[str]:
    try:
        return [r["instId"] for r in _get(ALL_SWAPS).get("data", []) if r.get("instId")]
    except Exception:
        return []


def history(inst_id: str) -> list[dict]:
    """Past settlements, oldest first. Each: {ts, rate, realized}."""
    try:
        rows = _get(HIST.format(inst_id)).get("data", [])
    except Exception:
        return []
    out = []
    for r in rows:
        try:
            out.append({"ts": int(r["fundingTime"]),
                        "rate": float(r["fundingRate"]),
                        "realized": float(r.get("realizedRate") or r["fundingRate"])})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda x: x["ts"])


def episodes(inst_id: str, rows: list[dict] | None = None) -> list[dict]:
    """Find contiguous runs at a BELOW-DEFAULT interval — i.e. escalation episodes.

    The default interval is the symbol's modal gap (OKX assigns 8h or 4h per symbol;
    "Bybit = 8h" style assumptions are wrong for most of the book).
    """
    rows = history(inst_id) if rows is None else rows
    if len(rows) < 6:
        return []

    gaps = [(rows[i + 1]["ts"] - rows[i]["ts"]) / 3.6e6 for i in range(len(rows) - 1)]
    gaps = [round(g, 1) for g in gaps]
    default_h = Counter(gaps).most_common(1)[0][0]
    if default_h <= 0:
        return []

    out: list[dict] = []
    i = 0
    while i < len(gaps):
        if gaps[i] < default_h * 0.9:            # interval shrank => escalated
            j = i
            while j + 1 < len(gaps) and gaps[j + 1] < default_h * 0.9:
                j += 1
            # settlements: rows[i] is the TRIGGER (the capped one that caused it);
            # rows[i+1 .. j+1] are the shortened-interval settlements we could trade.
            trigger = rows[i]
            capture = rows[i + 1: j + 2]
            if not capture:
                i = j + 1
                continue
            # Receiving side is the sign of the trigger: if funding is positive, longs
            # pay shorts, so a short perp collects. Take that side for the whole episode.
            sign = 1.0 if trigger["rate"] >= 0 else -1.0
            cap_bps = float(sum(s["realized"] * sign for s in capture)) * 1e4
            trg_bps = float(trigger["realized"] * sign) * 1e4
            out.append({
                "inst_id": inst_id,
                "start_ts": trigger["ts"], "end_ts": capture[-1]["ts"],
                "default_h": default_h,
                "min_interval_h": min(gaps[i: j + 1]),
                "n_settlements": len(capture),
                "duration_h": round((capture[-1]["ts"] - trigger["ts"]) / 3.6e6, 1),
                "trigger_bps": round(trg_bps, 2),      # already paid — NOT ours
                "capture_bps": round(cap_bps, 2),      # the only tradeable number
                "total_bps": round(trg_bps + cap_bps, 2),
                "direction": "short_perp" if sign > 0 else "long_perp",
            })
            i = j + 1
        else:
            i += 1
    return out


def verdict(eps: list[dict], bar_bps: float = 40.0) -> dict:
    """Apply the PRE-REGISTERED bar to `capture_bps` — never to `total_bps`."""
    if not eps:
        return {"n": 0, "verdict": "NO EPISODES"}
    cap = np.array([e["capture_bps"] for e in eps], dtype=float)
    trg = np.array([e["trigger_bps"] for e in eps], dtype=float)
    dur = np.array([e["duration_h"] for e in eps], dtype=float)
    med = float(np.median(cap))
    return {
        "n": len(eps),
        "median_capture_bps": round(med, 2),
        "mean_capture_bps": round(float(cap.mean()), 2),
        "median_trigger_bps": round(float(np.median(trg)), 2),
        "pct_of_money_in_trigger": round(float(
            np.median(np.abs(trg) / np.maximum(np.abs(trg) + np.abs(cap), 1e-9))), 3),
        "median_duration_h": round(float(np.median(dur)), 1),
        "pct_clearing_bar": round(float((cap > bar_bps).mean()), 3),
        "bar_bps": bar_bps,
        "verdict": ("PASS -> gauntlet" if med > bar_bps else
                    f"REJECT — median capture {med:.2f}bps <= {bar_bps}bps bar"),
    }
