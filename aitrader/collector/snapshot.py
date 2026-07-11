"""Point-in-time market snapshot from Kraken Futures (public, no key).

Kraken is a US-regulated exchange, so its API works from US-based GitHub Actions
runners (unlike Bybit/Binance, which geo-block US). One call returns all perpetual
tickers with funding + open interest. Funding is normalized to a fractional rate
(fundingRate / price) so it's comparable across symbols; stamped with observation time.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

KRAKEN = "https://futures.kraken.com/derivatives/api/v3/tickers"

# our name -> Kraken perpetual symbol
SYMBOL_MAP = {
    "BTCUSDT": "PF_XBTUSD",
    "ETHUSDT": "PF_ETHUSD",
    "SOLUSDT": "PF_SOLUSD",
    "XRPUSDT": "PF_XRPUSD",
}

FIELDS = ["ts", "symbol", "price", "funding", "next_funding_ms",
          "open_interest", "oi_value", "turnover_24h", "chg_24h"]


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "aitrader/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fetch_snapshot(symbols: list[str]) -> list[dict]:
    """Return one row per symbol with current price, normalized funding, and OI."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        tickers = _get(KRAKEN).get("tickers", [])
    except Exception:
        return []
    by_sym = {t.get("symbol"): t for t in tickers}

    rows: list[dict] = []
    for s in symbols:
        t = by_sym.get(SYMBOL_MAP.get(s, ""))
        if not t or t.get("last") in (None, 0):
            continue
        try:
            last = float(t["last"])
            fr = t.get("fundingRate")
            funding = float(fr) / last if fr is not None and last else 0.0   # fractional, per-hour
            oi = float(t.get("openInterest", 0) or 0)
            open24 = t.get("open24h")
            rows.append({
                "ts": ts,
                "symbol": s,
                "price": last,
                "funding": funding,
                "next_funding_ms": 0,
                "open_interest": oi,
                "oi_value": oi * last,
                "turnover_24h": float(t.get("vol24h", 0) or 0) * last,
                "chg_24h": (last / float(open24) - 1) if open24 else 0.0,
            })
        except Exception:
            continue
    return rows
