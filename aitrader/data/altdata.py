"""Alternative data: crypto perpetual FUNDING RATE from Binance public API (no key).

Funding rate is a positioning/sentiment signal that is NOT in price: persistently
positive funding => leveraged longs are crowded (contrarian-bearish), negative =>
shorts crowded (contrarian-bullish). This is exactly the kind of orthogonal signal
that can add edge where price-only features cannot.

Free, keyless, paginated. Crypto only (equities have no funding).
"""
from __future__ import annotations

import json
import time
import urllib.request

import numpy as np
import pandas as pd

_BASE = "https://fapi.binance.com/fapi/v1/fundingRate"

# map our yfinance-style tickers to Binance perp symbols
SYMBOL_MAP = {"BTC-USD": "BTCUSDT", "ETH-USD": "ETHUSDT",
              "BNB-USD": "BNBUSDT", "SOL-USD": "SOLUSDT"}


def _get(url: str):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())


def binance_funding_daily(ticker: str, days: int = 1600) -> pd.DataFrame | None:
    """Return daily funding features for `ticker`, or None if unsupported/unreachable.

    Columns: funding_rate (daily mean), funding_z (20d z-score), funding_chg.
    """
    sym = SYMBOL_MAP.get(ticker)
    if sym is None:
        return None
    try:
        start_ms = int((time.time() - days * 86400) * 1000)
        rows = []
        while True:
            data = _get(f"{_BASE}?symbol={sym}&startTime={start_ms}&limit=1000")
            if not data:
                break
            rows += data
            if len(data) < 1000:
                break
            start_ms = data[-1]["fundingTime"] + 1
        if not rows:
            return None
    except Exception:
        return None

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["fundingTime"], unit="ms").dt.normalize()
    df["rate"] = df["fundingRate"].astype(float)
    daily = df.groupby("date")["rate"].mean().to_frame("funding_rate")
    daily["funding_z"] = (
        (daily["funding_rate"] - daily["funding_rate"].rolling(20).mean())
        / daily["funding_rate"].rolling(20).std()
    )
    daily["funding_chg"] = daily["funding_rate"].diff()
    return daily.replace([np.inf, -np.inf], np.nan)
