"""Perp delisting event study — the first PERCENT-scale candidate we have tested.

WHY THIS ONE (FORCED_FLOW_MAP.md §1.3): Bybit force-closes ALL open positions in a
delisted perp at a 30-min index average, on ~2 days notice. Holders cannot decline at
any price; their arb counterparties must unwind the hedged leg too; and market makers
rationally withdraw from a contract with a published death date. Price-insensitive forced
exits into deliberately thinning liquidity — the purest FORCED-SETTLE in the map.

WHY IT MATTERS THAT IT'S PERCENT-SCALE: every prior rejection died the same death — the
edge was bps-scale (liq_meanrev +1.34bps, xexch_arb spread gone in hours) and retail
round-trip cost is ~5bps+. We do not win bps games; market makers have 10x lower costs.
So we stop hunting bps and test something whose dislocation, if real, is in percent.

--------------------------------------------------------------------------------------
THE CONFOUND THAT DECIDES THIS — SELECTION BIAS.

Bybit delists coins that are ALREADY DYING. Its own DDM rule delists when last price
< 20x tickSize. So a coin cratering after a delisting announcement may simply be
continuing to crater — it would have done so with no announcement at all. Raw
post-announcement return is therefore a MEANINGLESS statistic here, however negative.

What we actually measure:
    pre_abn   = coin return - BTC return, over [t0-48h, t0]     (its own pre-existing drift)
    post_abn  = coin return - BTC return, over [t0, t0+48h]     (drift after the news)
    INCREMENTAL = post_abn - pre_abn        <- the only number that means anything

If the coin was already falling 20%/48h and keeps falling 20%/48h, INCREMENTAL is ~0 and
the announcement carried NO information — dead, no matter how ugly the raw return.

Every event is also its own control (same coin, adjacent windows), which handles the
selection bias without needing a matched sample of non-delisted dying coins.

--------------------------------------------------------------------------------------
PRE-REGISTERED BAR (research/hypotheses.json, fixed BEFORE any return was computed):
  * volume-weighted median INCREMENTAL must be more negative than -50bps ROUND TRIP.
    50bps is honest for a dying microcap perp: 5.5bps taker each way is only the fee —
    the spread on a contract with a death date is the real cost, and it widens exactly
    when we would want to trade.
  * MUST survive NOTIONAL WEIGHTING. This is our own red flag from liq_meanrev turned on
    ourselves: if the effect lives only in coins with negligible turnover, it is not a
    business — it is the $3.71-fill trap in a new costume. The volume-weighted number
    decides; the count-weighted one is reported only to expose the gap.

PRIOR (FORCED_FLOW_MAP.md §4.1): a predictable price response to PERP delisting is
UNVERIFIED folklore. The literature covers spot listings/delistings and regulatory
events — different objects. The mechanism is certain; the price response is not.
Expect rejection.

API NOTE: klines for CLOSED symbols look empty — the default returns the LATEST bars and
a delisted contract has none. Pass explicit start/end and the full history is there.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timezone

ANN = ("https://api.bybit.com/v5/announcements/index"
       "?locale=en-US&type=delistings&limit=50&page={}")
KLINE = ("https://api.bybit.com/v5/market/kline?category=linear&symbol={}"
         "&interval=60&start={}&end={}&limit=1000")

# `\s+` matters: live titles include "ORBSUSDT Perpetual  Contract" (double space).
RX_SYM = re.compile(r"Delisting of ([A-Z0-9]+USDT)\s+Perpetual\s+Contract", re.I)
RX_WHEN = re.compile(r"at\s+(\w+ \d+, \d{4}),\s*(\d+):(\d+)\s*(AM|PM)\s*UTC", re.I)

EVENT_FIELDS = ["symbol", "announce_ts", "delist_ts", "notice_h",
                "pre_abn_pct", "post_abn_pct", "incremental_pct",
                "pre_turnover_usd", "post_turnover_usd", "bars_pre", "bars_post"]

HOUR_MS = 3_600_000


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def fetch_announcements(max_pages: int = 12) -> list[dict]:
    out: list[dict] = []
    for p in range(1, max_pages + 1):
        try:
            lst = _get(ANN.format(p)).get("result", {}).get("list", [])
        except Exception:
            break
        if not lst:
            break
        out.extend(lst)
        time.sleep(0.12)
    return out


def _announce_ts(a: dict) -> int | None:
    """publishTime is absent on 32/448 records (7 of our 193 perp events).

    `dateTimestamp` is the fallback — it is NOT identical (matches publishTime on only 2%
    of records; it runs ~13 min earlier), but against a 48h event window that offset is
    immaterial. Returning None rather than guessing if neither exists.
    """
    for k in ("publishTime", "dateTimestamp"):
        v = a.get(k)
        if v:
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
    return None


def parse_events(rows: list[dict]) -> list[dict]:
    """Single USDT linear perp delistings only — the clean, tradeable subset."""
    out = []
    for a in rows:
        m = RX_SYM.search(a.get("title", ""))
        if not m:
            continue
        ts = _announce_ts(a)
        if ts is None:
            continue
        ev = {"symbol": m.group(1).upper(), "announce_ts": ts, "delist_ts": None}
        w = RX_WHEN.search(a.get("description", "") or "")
        if w:
            try:
                hh = int(w.group(2)) % 12 + (12 if w.group(4).upper() == "PM" else 0)
                dt = datetime.strptime(f"{w.group(1)} {hh}:{w.group(3)}", "%b %d, %Y %H:%M")
                ev["delist_ts"] = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
            except ValueError:
                pass
        out.append(ev)
    return out


def fetch_klines(symbol: str, start_ms: int, end_ms: int) -> list[list]:
    """Ascending [ts, o, h, l, c, vol, turnover]. Empty list on any failure."""
    try:
        r = _get(KLINE.format(symbol, start_ms, end_ms))
        return sorted(r.get("result", {}).get("list", []), key=lambda x: int(x[0]))
    except Exception:
        return []


def _ret_and_turnover(bars: list[list]) -> tuple[float | None, float, int]:
    """close-to-close return, total USD turnover, bar count."""
    if len(bars) < 2:
        return None, 0.0, len(bars)
    try:
        c0, c1 = float(bars[0][4]), float(bars[-1][4])
        if c0 <= 0:
            return None, 0.0, len(bars)
        turn = sum(float(b[6]) for b in bars)
        return c1 / c0 - 1.0, turn, len(bars)
    except (ValueError, IndexError):
        return None, 0.0, len(bars)


def launch_time(symbol: str) -> int:
    """0 if unknown. Used to detect RELISTS — see study_event."""
    try:
        l = _get(f"https://api.bybit.com/v5/market/instruments-info"
                 f"?category=linear&symbol={symbol}").get("result", {}).get("list", [])
        lt = l[0].get("launchTime") if l else None
        return int(lt) if lt and lt != "0" else 0
    except Exception:
        return 0


def study_event(ev: dict, window_h: int = 48) -> dict:
    """One event, its own control: same coin, adjacent windows, BTC-adjusted.

    Always returns a dict. On failure it carries `skip` — a REASON, never a silent drop.
    A study that quietly discards events is a study that quietly chooses its own sample.
    """
    t0 = ev["announce_ts"]
    a, b, c = t0 - window_h * HOUR_MS, t0, t0 + window_h * HOUR_MS

    # RELIST TRAP: Bybit reuses tickers. If the CURRENT listing launched after this
    # announcement, the symbol was delisted and later re-listed, and the kline API serves
    # only the current instance — the old history is gone. Those events would return zero
    # bars and vanish from the sample silently. They must not: a coin that got re-listed
    # is precisely a coin that did NOT stay dead, so dropping them biases the study toward
    # permanently-dead names, i.e. toward MORE negative returns — flattering the strategy.
    # Measured 2026-07-17: 5 of 193 events (2.6%).
    lt = launch_time(ev["symbol"])
    if lt and lt > a:
        return {"symbol": ev["symbol"], "skip": "relisted — old history unavailable"}

    pre = fetch_klines(ev["symbol"], a, b)
    post = fetch_klines(ev["symbol"], b, c)
    btc_pre = fetch_klines("BTCUSDT", a, b)
    btc_post = fetch_klines("BTCUSDT", b, c)

    r_pre, turn_pre, n_pre = _ret_and_turnover(pre)
    r_post, turn_post, n_post = _ret_and_turnover(post)
    rb_pre, _, _ = _ret_and_turnover(btc_pre)
    rb_post, _, _ = _ret_and_turnover(btc_post)
    if r_pre is None or r_post is None:
        return {"symbol": ev["symbol"],
                "skip": f"no coin klines (pre {n_pre} bars, post {n_post} bars)"}
    if rb_pre is None or rb_post is None:
        return {"symbol": ev["symbol"], "skip": "no BTC benchmark klines"}

    pre_abn = r_pre - rb_pre
    post_abn = r_post - rb_post
    return {
        "symbol": ev["symbol"],
        "announce_ts": datetime.fromtimestamp(t0 / 1000, timezone.utc).isoformat(timespec="seconds"),
        "delist_ts": (datetime.fromtimestamp(ev["delist_ts"] / 1000, timezone.utc)
                      .isoformat(timespec="seconds") if ev["delist_ts"] else None),
        "notice_h": (round((ev["delist_ts"] - t0) / HOUR_MS, 1) if ev["delist_ts"] else None),
        "pre_abn_pct": round(pre_abn * 100, 3),
        "post_abn_pct": round(post_abn * 100, 3),
        "incremental_pct": round((post_abn - pre_abn) * 100, 3),   # THE number
        "pre_turnover_usd": round(turn_pre, 0),
        "post_turnover_usd": round(turn_post, 0),
        "bars_pre": n_pre, "bars_post": n_post,
    }
