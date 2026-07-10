"""Fetch a point-in-time market snapshot from Bybit (public, no key, not geo-blocked).

One call per symbol returns price + funding + open interest + 24h stats. Each row is
stamped with the UTC time it was observed — so the stored history is lookahead-free.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

BYBIT = "https://api.bybit.com/v5/market/tickers?category=linear&symbol={}"

FIELDS = ["ts", "symbol", "price", "funding", "next_funding_ms",
          "open_interest", "oi_value", "turnover_24h", "chg_24h"]


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "aitrader/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fetch_snapshot(symbols: list[str]) -> list[dict]:
    """Return one row per symbol with the current observable market state."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict] = []
    for s in symbols:
        try:
            d = _get(BYBIT.format(s))
            t = d["result"]["list"][0]
            rows.append({
                "ts": ts,
                "symbol": s,
                "price": float(t["lastPrice"]),
                "funding": float(t["fundingRate"]),
                "next_funding_ms": int(t.get("nextFundingTime", 0) or 0),
                "open_interest": float(t.get("openInterest", 0) or 0),
                "oi_value": float(t.get("openInterestValue", 0) or 0),
                "turnover_24h": float(t.get("turnover24h", 0) or 0),
                "chg_24h": float(t.get("price24hPcnt", 0) or 0),
            })
        except Exception:
            continue
    return rows
