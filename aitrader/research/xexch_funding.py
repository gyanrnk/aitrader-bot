"""Cross-exchange funding-rate arbitrage — a STRUCTURAL edge (not a prediction).

Same perpetual, different exchanges, different funding rates (fragmented liquidity).
Go LONG on the exchange paying longs (negative funding) + SHORT on the exchange paying
shorts (positive funding) => market-neutral, collect the funding SPREAD.

Honest: snapshot spreads look big but are momentary (funding mean-reverts every 8h) and
you pay costs on BOTH legs + need capital on BOTH exchanges. The captured edge is much
smaller than the headline spread. So we LOG spreads over time to see if they PERSIST
(real, capturable) or are just noise. All data free, no keys.

Funding conventions normalized to annualized %:
  Kraken Futures: fundingRate/price per hour  -> x 24 x 365
  OKX / Bybit:    fundingRate per 8h           -> x 3  x 365
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

COINS = ["BTC", "ETH", "SOL", "XRP"]


def _get(url: str, ua: str = "aitrader/0.1") -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _kraken() -> dict:
    m = {"PF_XBTUSD": "BTC", "PF_ETHUSD": "ETH", "PF_SOLUSD": "SOL", "PF_XRPUSD": "XRP"}
    out = {}
    try:
        for t in _get("https://futures.kraken.com/derivatives/api/v3/tickers")["tickers"]:
            if t.get("symbol") in m and t.get("last"):
                out[m[t["symbol"]]] = float(t["fundingRate"]) / float(t["last"]) * 24 * 365 * 100
    except Exception:
        pass
    return out


def _okx() -> dict:
    out = {}
    for c in COINS:
        try:
            d = _get(f"https://www.okx.com/api/v5/public/funding-rate?instId={c}-USDT-SWAP")
            out[c] = float(d["data"][0]["fundingRate"]) * 3 * 365 * 100
        except Exception:
            pass
    return out


def _bybit() -> dict:
    out = {}
    try:
        d = _get("https://api.bybit.com/v5/market/tickers?category=linear")
        for t in d["result"]["list"]:
            s = t.get("symbol", "")
            if s in [f"{c}USDT" for c in COINS] and t.get("fundingRate"):
                out[s.replace("USDT", "")] = float(t["fundingRate"]) * 3 * 365 * 100
    except Exception:
        pass                       # Bybit geo-blocks US (GitHub); works locally / India
    return out


def fetch_cross_funding() -> list[dict]:
    """Return per-coin cross-exchange funding + the arb spread and legs."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    k, o, b = _kraken(), _okx(), _bybit()
    rows = []
    for c in COINS:
        vals = {ex: v for ex, v in (("kraken", k.get(c)), ("okx", o.get(c)),
                                    ("bybit", b.get(c))) if v is not None}
        if len(vals) < 2:
            continue
        hi_ex, hi = max(vals.items(), key=lambda x: x[1])   # short here (receive +funding)
        lo_ex, lo = min(vals.items(), key=lambda x: x[1])   # long here  (receive -funding)
        rows.append({
            "ts": ts, "coin": c,
            "kraken": round(k.get(c, float("nan")), 2),
            "okx": round(o.get(c, float("nan")), 2),
            "bybit": round(b.get(c, float("nan")), 2),
            "spread_pct": round(hi - lo, 2),               # gross annualized arb (before costs)
            "short_on": hi_ex, "long_on": lo_ex,
        })
    return rows


XFUNDING_FIELDS = ["ts", "coin", "kraken", "okx", "bybit", "spread_pct", "short_on", "long_on"]
