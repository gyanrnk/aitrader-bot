"""Kraken Futures liquidation history — the one forced flow with free, deep history.

Why this file exists (see FORCED_FLOW_MAP.md §1.1, §8): liquidations are the ONLY
genuinely forced, price-insensitive flow in the map that ALSO has free, order-level
history back to 2022-03-23 on an unauthenticated endpoint. Everything else either
isn't actually forced (funding "dodge" — elective), isn't observable (ADL queue —
private), or has no history at all (diff-based regime flags).

Hypothesis under test (registry id: `liq_meanrev`):
    "Forced liquidations overshoot price; I provide liquidity into the cascade and fade it."

THE DECISIVE MEASUREMENT IS NOT A BACKTEST. Every execution carries the mark price at
that instant, so the dislocation is DIRECTLY observable — no modelling, no lookahead:

    dislocation = (fill_price - mark_price) / mark_price

A forced SELL (a long being liquidated) must fill BELOW mark for the premise to hold.
If forced sells fill AT or ABOVE mark, there is no discount to capture and the idea is
dead — measured in minutes instead of a week of backtest engineering. Sign convention
below folds direction in, so `adverse_bps > 0` always means "filled worse than mark",
i.e. a discount WE could have collected by taking the other side.

Traps, all verified live 2026-07-17 (FORCED_FLOW_MAP.md §1.1, §7):
  * The documented `orderType` enum omits BOTH `PartialLiquidation` and `FillOrKill`,
    yet live data returns them. `PartialLiquidation` is the COMMON one — filtering on
    the documented enum silently drops most liquidations. Match substring, not equality.
  * `before=` is INCLUSIVE (returns a record AT the boundary) -> paginate with
    `continuationToken`, never by rolling timestamps, or you double-count.
  * `count` caps at 1000 no matter what you ask for (5000 -> 1000).
  * Liquidations are RARE and CLUSTERED: ~0.36% of executions on DOGE; 0/1000 on
    BTC/ETH/SOL/XRP in a calm probe. Budget pages accordingly.

Throughput measured: ~0.92 s/page, 1000 execs/page, ~3.6 h of tape per page (DOGE).
=> full 4.3y history ~= 10,500 pages ~= 2.7 h per symbol. A slice is enough to start.
"""
from __future__ import annotations

import json
import urllib.request

BASE = "https://futures.kraken.com/api/history/v3/market/{}/executions"

# our four majors + the retail-heavy names where liquidations actually live
SYMBOLS = ["PF_XBTUSD", "PF_ETHUSD", "PF_SOLUSD", "PF_XRPUSD", "PF_DOGEUSD"]

LIQ_FIELDS = ["ts", "symbol", "order_type", "direction", "qty", "usd_value",
              "limit_price", "fill_price", "mark_price", "limit_filled",
              "adverse_bps", "maker_reduce_only"]


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "aitrader/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def is_liquidation(order_type: str) -> bool:
    """Substring match — the docs' enum is stale and misses `PartialLiquidation`."""
    return "liquidat" in (order_type or "").lower()


def fetch_page(symbol: str, token: str | None = None, count: int = 1000):
    """One page, newest-first. Returns (elements, next_token)."""
    url = BASE.format(symbol) + f"?sort=desc&count={count}"
    if token:
        url += f"&continuationToken={token}"
    d = _get(url)
    return d.get("elements", []), d.get("continuationToken")


def parse(e: dict, symbol: str) -> dict | None:
    """Flatten one execution. Returns None if it isn't a liquidation."""
    ex = e.get("event", {}).get("Execution", {}).get("execution", {})
    taker = ex.get("takerOrder", {})
    ot = taker.get("orderType", "")
    if not is_liquidation(ot):
        return None
    try:
        fill = float(ex["price"])
        mark = float(ex["markPrice"])
        direction = taker.get("direction")          # Sell => a LONG was liquidated
    except (KeyError, TypeError, ValueError):
        return None
    if not mark:
        return None

    # Sign so that POSITIVE = filled WORSE than mark = a discount we could have taken.
    #   forced Sell  -> adverse if fill < mark
    #   forced Buy   -> adverse if fill > mark
    raw_bps = (fill - mark) / mark * 1e4
    adverse_bps = -raw_bps if direction == "Sell" else raw_bps

    return {
        "ts": e.get("timestamp"),
        "symbol": symbol,
        "order_type": ot,
        "direction": direction,
        "qty": float(taker.get("quantity", 0) or 0),
        "usd_value": float(ex.get("usdValue", 0) or 0),
        "limit_price": float(taker.get("limitPrice", 0) or 0),
        "fill_price": fill,
        "mark_price": mark,
        "limit_filled": bool(ex.get("limitFilled")),
        "adverse_bps": round(adverse_bps, 3),
        "maker_reduce_only": bool(ex.get("makerOrder", {}).get("reduceOnly")),
    }


def pull(symbol: str, max_pages: int = 50, progress=None) -> dict:
    """Walk the tape newest-first, keeping only liquidations.

    Returns {'liquidations': [...], 'n_execs': int, 'pages': int,
             'first_ts': ms, 'last_ts': ms}.
    """
    token = None
    liqs: list[dict] = []
    n_execs = 0
    first_ts = last_ts = None
    pages = 0

    for i in range(max_pages):
        els, token = fetch_page(symbol, token)
        if not els:
            break
        pages += 1
        n_execs += len(els)
        if first_ts is None:
            first_ts = els[0].get("timestamp")
        last_ts = els[-1].get("timestamp")
        for e in els:
            row = parse(e, symbol)
            if row:
                liqs.append(row)
        if progress and (i + 1) % 10 == 0:
            progress(symbol, pages, n_execs, len(liqs))
        if not token:
            break

    return {"liquidations": liqs, "n_execs": n_execs, "pages": pages,
            "first_ts": first_ts, "last_ts": last_ts}
