"""Multi-market point-in-time snapshot — all free, all cloud-accessible (no geo-block).

  * Crypto  -> Kraken Futures (price + funding + open interest)
  * Stocks / indices / forex / commodities -> Yahoo chart API (price only)

Non-crypto rows carry funding=0, oi=0 (those don't exist for stocks/forex) — the signal
layer then runs momentum-only for them. Every row is stamped with observation time, so
the stored history stays lookahead-free. One shared timestamp per collection cycle.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

KRAKEN = "https://futures.kraken.com/derivatives/api/v3/tickers"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{}?range=1d&interval=1d"

# crypto: our name -> Kraken perpetual symbol
CRYPTO_MAP = {
    "BTCUSDT": "PF_XBTUSD", "ETHUSDT": "PF_ETHUSD",
    "SOLUSDT": "PF_SOLUSD", "XRPUSDT": "PF_XRPUSD",
}

FIELDS = ["ts", "symbol", "price", "funding", "next_funding_ms",
          "open_interest", "oi_value", "turnover_24h", "chg_24h"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(url: str, ua: str = "aitrader/0.1") -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fetch_snapshot(symbols: list[str], ts: str | None = None) -> list[dict]:
    """Crypto snapshot from Kraken (price + normalized funding + OI)."""
    ts = ts or _now()
    try:
        tickers = _get(KRAKEN).get("tickers", [])
    except Exception:
        return []
    by_sym = {t.get("symbol"): t for t in tickers}
    rows = []
    for s in symbols:
        t = by_sym.get(CRYPTO_MAP.get(s, ""))
        if not t or t.get("last") in (None, 0):
            continue
        try:
            last = float(t["last"])
            fr = t.get("fundingRate")
            funding = float(fr) / last if fr is not None and last else 0.0
            oi = float(t.get("openInterest", 0) or 0)
            open24 = t.get("open24h")
            rows.append({"ts": ts, "symbol": s, "price": last, "funding": funding,
                         "next_funding_ms": 0, "open_interest": oi, "oi_value": oi * last,
                         "turnover_24h": float(t.get("vol24h", 0) or 0) * last,
                         "chg_24h": (last / float(open24) - 1) if open24 else 0.0})
        except Exception:
            continue
    return rows


def fetch_yahoo(mapping: dict[str, str], ts: str | None = None) -> list[dict]:
    """Stocks / indices / forex / commodities from Yahoo (price only; funding/OI = 0)."""
    ts = ts or _now()
    rows = []
    for name, ysym in mapping.items():
        try:
            m = _get(YAHOO.format(ysym), ua="Mozilla/5.0")["chart"]["result"][0]["meta"]
            price = float(m["regularMarketPrice"])
            prev = m.get("previousClose") or m.get("chartPreviousClose") or price
            vol = float(m.get("regularMarketVolume", 0) or 0)
            rows.append({"ts": ts, "symbol": name, "price": price, "funding": 0.0,
                         "next_funding_ms": 0, "open_interest": 0.0, "oi_value": 0.0,
                         "turnover_24h": vol * price,
                         "chg_24h": (price / float(prev) - 1) if prev else 0.0})
        except Exception:
            continue
    return rows
