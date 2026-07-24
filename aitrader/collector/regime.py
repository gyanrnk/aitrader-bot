"""OKX funding-interval regime flag — a free public signal almost nobody polls.

WHY (FORCED_FLOW_MAP.md §2.1): OKX publishes a deterministic rule — when a perp's funding
rate hits its cap/floor AT SETTLEMENT, the settlement frequency escalates one level:

    8h -> 4h -> 2h -> 1h

The economics are large because the `8/N` divisor lands BEFORE the clamp. With a sustained
premium P and a 0.375% cap:

    N=8h:  min(P, 0.375%) per 8h   -> max 1.125%/day   (CAPPED — funding is NOT clearing)
    N=1h:  min(P/8, 0.375%) per 1h -> min(3P, 9%)/day  (uncapped — funding clears again)

At P=1% that is 1.125%/day vs 3.00%/day. Escalation UN-CLAMPS funding and restores up to
8x the daily carry. And while the cap binds, funding stops disciplining the basis at all —
the paying side is subsidised, so a rich basis has no reason to close. THE CAP IS WHY A
RICH BASIS STAYS RICH.

THE ASYMMETRY THAT MATTERS: escalation is a published, deterministic, observable rule.
De-escalation is NOT — OKX reverts "without further notice", with no stated threshold,
count, or timeframe. Do not model this as symmetric.

WHY THIS FILE EXISTS AT ALL — the data has NO history. `nextFundingTime`/`fundingTime` are
live-only; you cannot backfill the interval a symbol had last Tuesday. The signal lives in
the CHANGE BETWEEN POLLS, so every day we don't snapshot is lost permanently. That is the
whole reason this ships before any strategy is written.

STORAGE: we do NOT store 510 symbols x 144 polls/day (=73k rows/day of mostly nothing).
We store the DIFF — interval changes and cap binds — plus a tiny per-poll distribution
summary so the regime time-series is reconstructable.

CLOUD-SAFE: OKX is reachable from GitHub Actions runners. (Bybit is geo-blocked there —
verified: bybit present in only 4/1036 xfunding rows — so Bybit's equivalent flag can only
be collected from a local/India run. Not wired here.)

One call: `instId=ANY` returns the entire book (510 swaps, ~0.2s). No per-symbol fanout.
"""
from __future__ import annotations

import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OKX_FUNDING = "https://www.okx.com/api/v5/public/funding-rate?instId=ANY"
OKX_BORROW = "https://www.okx.com/api/v5/public/interest-rate-loan-quota"

# R8 (napkin): can we legally reach the venue we'd have to trade on?
#
# okx.com returns a MeitY block page in India under the IT Act, 2000 (observed
# 2026-07-24). The DATA still flows — the collector runs on GitHub Actions runners in the
# US — so research, episode recording and the escalation dataset are unaffected. What is
# closed is EXECUTION.
#
# Why this constant exists rather than just switching the alert off: an alert that keeps
# emailing "GO SIGNAL" for a venue we cannot trade is worse than no alert. It trains you
# to chase something unreachable, and the only way to act on it would be to circumvent a
# government block — which is not an edge, it is legal exposure with no recourse.
#
# So: keep detecting, keep recording, and mark the finding RESEARCH-ONLY instead of
# raising it as actionable. If OKX is ever unblocked (or we operate from a jurisdiction
# where it is reachable), flip this one flag and the alert path comes back.
VENUE_TRADEABLE = {"okx": False}
VENUE_BLOCK_REASON = {
    "okx": "okx.com blocked in India by MeitY order under the IT Act, 2000 "
           "(observed 2026-07-24). Data still readable from cloud runners; execution is not."
}

# Control coins: deep, liquid borrow pools that should NOT move during a microcap
# episode. Without them we cannot tell a coin-specific borrow squeeze from a
# market-wide rate change.
BORROW_CONTROLS = ("BTC", "ETH", "USDT")

BORROW_FIELDS = ["ts", "ccy", "rate", "quota", "reason", "inst_id", "interval_h"]

EVENT_FIELDS = ["ts", "inst_id", "event", "old", "new", "funding_rate",
                "sett_funding_rate", "cap", "floor", "interval_h", "premium"]
SUMMARY_FIELDS = ["ts", "n_symbols", "n_1h", "n_2h", "n_4h", "n_8h", "n_other",
                  "n_pinned_live", "n_at_cap_sett", "n_events"]

CAP_TOL = 0.99          # |rate| >= 0.99*cap counts as "at the cap"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "aitrader/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fetch_okx_regime() -> dict[str, dict]:
    """One call -> {instId: {interval_h, funding_rate, cap, at_cap, premium, ...}}."""
    out: dict[str, dict] = {}
    try:
        rows = _get(OKX_FUNDING).get("data", [])
    except Exception:
        return out
    for r in rows:
        inst = r.get("instId")
        if not inst:
            continue
        try:
            ft, nft = int(r["fundingTime"]), int(r["nextFundingTime"])
            interval_h = round((nft - ft) / 3.6e6, 2)
            rate = float(r.get("fundingRate") or 0)
            cap = float(r.get("maxFundingRate") or 0)
            floor = float(r.get("minFundingRate") or 0)
            sett = float(r.get("settFundingRate") or 0) if r.get("settFundingRate") else None
        except (KeyError, TypeError, ValueError):
            continue
        out[inst] = {
            "interval_h": interval_h,
            "funding_rate": rate,
            "sett_funding_rate": sett,
            "cap": cap,
            "floor": floor,
            # TWO different questions, and we want both:
            #   at_cap_sett = the SETTLED rate hit the cap  -> the documented escalation
            #                 TRIGGER. Tells us it already happened.
            #   at_cap_live = the CURRENT (still-updating) rate is pinned at the cap
            #                 -> PREDICTIVE. Escalation is likely at the next settlement.
            # The live flag is the interesting one: it is the only forward-looking read OKX
            # leaves us, since `nextFundingRate` is empty on 509/509 (current_period).
            "at_cap_sett": _pinned(sett, cap, floor),
            "at_cap_live": _pinned(rate, cap, floor),
            "premium": float(r.get("premium") or 0),
            "sett_state": r.get("settState"),
        }
    return out


def _pinned(rate: float | None, cap: float, floor: float) -> bool:
    """At/near either bound. Caps are usually symmetric but do not assume it."""
    if rate is None:
        return False
    if cap and rate >= cap * CAP_TOL:
        return True
    if floor and rate <= floor * CAP_TOL:
        return True
    return False


def diff(prev: dict[str, dict], curr: dict[str, dict], ts: str) -> list[dict]:
    """Emit only what CHANGED. This is the signal; the levels are not."""
    events: list[dict] = []

    def ev(inst, name, old, new, s):
        events.append({
            "ts": ts, "inst_id": inst, "event": name, "old": old, "new": new,
            "funding_rate": round(s["funding_rate"], 8),
            "sett_funding_rate": (None if s.get("sett_funding_rate") is None
                                  else round(s["sett_funding_rate"], 8)),
            "cap": s.get("cap"), "floor": s.get("floor"),
            "interval_h": s["interval_h"],
            "premium": round(s["premium"], 8),
        })

    for inst, s in curr.items():
        p = prev.get(inst)
        if p is None:
            if prev:                      # don't fire on first-ever run
                ev(inst, "listed", None, s["interval_h"], s)
            continue
        if p.get("interval_h") != s["interval_h"]:
            # THE flag. Down = escalation (rule-based). Up = de-escalation (discretionary).
            name = ("escalate" if s["interval_h"] < p["interval_h"] else "de_escalate")
            ev(inst, name, p["interval_h"], s["interval_h"], s)
        # live pin = forward-looking (escalation likely next settlement)
        if bool(p.get("at_cap_live")) != bool(s["at_cap_live"]):
            ev(inst, "pin_start" if s["at_cap_live"] else "pin_end",
               p.get("at_cap_live"), s["at_cap_live"], s)
        # settled pin = the documented escalation trigger actually firing
        if bool(p.get("at_cap_sett")) != bool(s["at_cap_sett"]):
            ev(inst, "cap_bind" if s["at_cap_sett"] else "cap_release",
               p.get("at_cap_sett"), s["at_cap_sett"], s)

    for inst in prev:
        if inst not in curr:
            ev(inst, "delisted", prev[inst].get("interval_h"), None,
               {"funding_rate": 0, "sett_funding_rate": None, "cap": 0,
                "interval_h": 0, "premium": 0})
    return events


def summarize(curr: dict[str, dict], ts: str, n_events: int) -> dict:
    """Per-poll distribution — tiny, but makes the regime time-series reconstructable."""
    b = {1: 0, 2: 0, 4: 0, 8: 0}
    other = pinned = bound = 0
    for s in curr.values():
        h = int(s["interval_h"]) if float(s["interval_h"]).is_integer() else None
        if h in b:
            b[h] += 1
        else:
            other += 1
        pinned += bool(s["at_cap_live"])
        bound += bool(s["at_cap_sett"])
    return {"ts": ts, "n_symbols": len(curr), "n_1h": b[1], "n_2h": b[2],
            "n_4h": b[4], "n_8h": b[8], "n_other": other,
            "n_pinned_live": pinned, "n_at_cap_sett": bound, "n_events": n_events}


def _ticker_last(inst_id: str) -> float | None:
    """Last price for any OKX instrument; None if it doesn't exist / call fails."""
    try:
        d = _get(f"https://www.okx.com/api/v5/market/ticker?instId={inst_id}")
        return float(d["data"][0]["last"])
    except Exception:
        return None


def episode_rows(curr: dict[str, dict], brows: list[dict], ts: str) -> list[dict]:
    """One full-detail row per flagged instrument per cycle -> okx_episodes.csv.

    Everything except prices is already in hand: `brows` carries the borrow terms and
    `curr` the funding state. Prices cost two extra API calls per flagged symbol;
    episodes are rare (0-3 live at a time), so a quiet market costs nothing.
    """
    out = []
    for b in brows:
        if b["reason"] == "control" or not b.get("inst_id"):
            continue
        s = curr.get(b["inst_id"])
        if not s:
            continue
        out.append({
            "ts": ts, "inst_id": b["inst_id"], "ccy": b["ccy"],
            "interval_h": s["interval_h"],
            "funding_rate": s["funding_rate"],
            "cap": s.get("cap"), "floor": s.get("floor"),
            "at_cap_live": bool(s.get("at_cap_live")),
            "at_cap_sett": bool(s.get("at_cap_sett")),
            "borrowable": "NOT_BORROWABLE" not in b["reason"],
            "borrow_rate": b.get("rate"),
            "borrow_quota": b.get("quota"),
            "perp_last": _ticker_last(b["inst_id"]),
            "spot_last": _ticker_last(f'{b["ccy"]}-USDT'),
        })
    return out


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------- borrow-side tracking
#
# WHY: `funding_escalation` is our only surviving idea, and the single question that
# decides it is one history cannot answer — CAN WE ACTUALLY BORROW WHEN IT MATTERS?
#
# 9 of 10 measured episodes had NEGATIVE funding, so collecting means LONG perp, so the
# delta-neutral hedge is SHORT SPOT, which requires borrowing the coin. The uncomfortable
# hypothesis is that funding sits pinned at the cap PRECISELY BECAUSE the borrow is
# unavailable — if it were free, someone would short spot / long perp and funding would
# normalise. On that reading the tiny quota (LRC $2,174) is not a capacity ceiling, it is
# the REASON the opportunity exists, and every would-be arbitrageur is competing for the
# same exhausted pool exactly when we want it.
#
# WHAT WE CAN AND CANNOT SEE. OKX's public endpoint returns only `ccy`, `quota`, `rate` —
# the MAXIMUM quota and the base rate. It does NOT expose live pool availability, so we
# cannot observe exhaustion directly. But OKX raises the borrow rate dynamically under
# demand, so a RATE SPIKE on the escalating coin (while BTC/ETH/USDT stay flat) is
# evidence of a borrow squeeze. That is a proxy, not proof.
#
# HONEST LIMIT: the rate may not move at all even when the pool is empty — OKX can simply
# reject the borrow. Only an authenticated account attempting a real borrow settles this.
# This snapshot narrows the question; it does not close it.


def fetch_borrow() -> dict[str, dict]:
    """{ccy: {rate, quota}} — public, no auth. Empty dict on failure."""
    try:
        d = _get(OKX_BORROW).get("data", [])
    except Exception:
        return {}
    out: dict[str, dict] = {}
    for block in d:
        for r in block.get("basic", []) or []:
            try:
                out[r["ccy"]] = {"rate": float(r["rate"]), "quota": float(r["quota"])}
            except (KeyError, TypeError, ValueError):
                continue
    return out


def borrow_rows(curr: dict[str, dict], ts: str) -> list[dict]:
    """Snapshot borrow terms for coins that are ESCALATED or PINNED, plus controls.

    We deliberately do not snapshot all 500+ symbols: the signal is what happens to the
    borrow of a coin while it is in an extreme funding state, against a flat control.
    """
    interesting: dict[str, tuple[str, str, float]] = {}
    for inst, s in curr.items():
        base = inst.split("-")[0]
        if s.get("at_cap_live") or s.get("at_cap_sett"):
            interesting[base] = ("pinned_at_cap", inst, s["interval_h"])
        elif s["interval_h"] < 4:
            # ONLY 1h and 2h are unambiguously escalated. OKX assigns 8h OR 4h as the
            # per-symbol DEFAULT (currently 286 vs 225 of the book), so "< 8h" would flag
            # every 4h-default symbol as escalated — 200 rows of noise per poll, drowning
            # the signal. This is the same per-symbol-default trap documented in
            # research/escalation.py, and it bit again here.
            interesting.setdefault(base, ("short_interval", inst, s["interval_h"]))

    if not interesting:
        return []                       # nothing in an extreme state — don't log noise

    borrow = fetch_borrow()
    if not borrow:
        return []
    rows = []
    for ccy in list(interesting) + list(BORROW_CONTROLS):
        b = borrow.get(ccy)
        if not b:
            # not borrowable at all — itself the decisive fact for that coin
            reason, inst, iv = interesting.get(ccy, ("control", "", 0.0))
            rows.append({"ts": ts, "ccy": ccy, "rate": None, "quota": 0.0,
                         "reason": f"{reason}|NOT_BORROWABLE", "inst_id": inst,
                         "interval_h": iv})
            continue
        reason, inst, iv = interesting.get(ccy, ("control", "", 0.0))
        rows.append({"ts": ts, "ccy": ccy, "rate": b["rate"], "quota": b["quota"],
                     "reason": reason, "inst_id": inst, "interval_h": iv})
    return rows


# ---------------------------------------------------------------- persistence

STORE = Path(__file__).resolve().parents[2] / "data" / "regime"
STATE = STORE / "okx_state.json"
EVENTS = STORE / "okx_events.csv"
SUMMARY = STORE / "okx_summary.csv"
BORROW = STORE / "okx_borrow.csv"
EPISODES = STORE / "okx_episodes.csv"

# Full per-cycle record of every live episode. Two jobs at once:
#   1. SURVIVORSHIP FIX — a delisted symbol's funding history vanishes from OKX's API
#      (LRC returns 0 rows now), so our historical study could only see the coins that
#      survived. Recording AT THE TIME, while the coin still exists, closes that hole.
#   2. PAPER P&L INPUT — with funding, perp and spot prices captured per cycle, a
#      delta-neutral paper simulation for any episode (incl. a GO episode) can be
#      computed later from this file alone. Collection stays dumb; analysis stays free.
EPISODE_FIELDS = ["ts", "inst_id", "ccy", "interval_h", "funding_rate", "cap", "floor",
                  "at_cap_live", "at_cap_sett", "borrowable", "borrow_rate",
                  "borrow_quota", "perp_last", "spot_last"]


def _append(path: Path, fields: list[str], rows: list[dict]) -> None:
    if not rows:
        return
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def step() -> dict:
    """One poll: fetch -> diff against last state -> append events + summary -> save state.

    Safe to call every collector cycle. Returns a short dict for the run log.
    """
    curr = fetch_okx_regime()
    if not curr:
        return {"ok": False, "reason": "OKX unreachable"}

    STORE.mkdir(parents=True, exist_ok=True)
    prev = {}
    if STATE.exists():
        try:
            prev = json.loads(STATE.read_text() or "{}")
        except Exception:
            prev = {}

    ts = now_iso()
    events = diff(prev, curr, ts)
    _append(EVENTS, EVENT_FIELDS, events)
    _append(SUMMARY, SUMMARY_FIELDS, [summarize(curr, ts, len(events))])

    # Borrow terms for anything in an extreme state — only fetched when something is
    # actually escalated/pinned, so a quiet market costs one extra request and no rows.
    brows = borrow_rows(curr, ts)
    _append(BORROW, BORROW_FIELDS, brows)

    # Full episode record (funding + borrow + prices) — the survivorship fix AND the
    # raw input for paper P&L simulation of any episode, including a future GO.
    _append(EPISODES, EPISODE_FIELDS, episode_rows(curr, brows, ts))

    STATE.write_text(json.dumps(curr, indent=None, separators=(",", ":")))

    # THE GO SIGNAL: an escalated/pinned coin that is ALSO borrowable — the one condition
    # every episode so far has failed (LRC delisted; LA/ONE/O not borrowable). borrow_rows
    # already carries exactly this: a non-control row WITHOUT the NOT_BORROWABLE marker.
    go = [r for r in brows
          if r["reason"] != "control" and "NOT_BORROWABLE" not in r["reason"]]

    # R8 gate: a GO on an unreachable venue is research, not an opportunity. Keep it in
    # the return value (the dashboard still shows it, the recorder still stores it) but
    # do NOT let it become an actionable alert.
    tradeable = VENUE_TRADEABLE.get("okx", True)

    hot = [e for e in events if e["event"] in ("escalate", "cap_bind", "pin_start")]
    return {"ok": True, "symbols": len(curr), "events": len(events),
            "escalations": sum(1 for e in events if e["event"] == "escalate"),
            "pinned_live_now": sum(1 for s in curr.values() if s["at_cap_live"]),
            "at_cap_sett_now": sum(1 for s in curr.values() if s["at_cap_sett"]),
            "borrow_rows": len(brows),
            "go_signals": go if tradeable else [],   # alert path — R8 gated
            "go_research_only": [] if tradeable else go,
            "venue_tradeable": tradeable,
            "venue_block_reason": None if tradeable else VENUE_BLOCK_REASON.get("okx"),
            "hot": [f'{e["inst_id"]}:{e["event"]}:{e["old"]}->{e["new"]}' for e in hot[:5]]}
