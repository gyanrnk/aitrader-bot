"""Stage 2 — point-in-time funding-rate data (Binance public API, no keys).

Each funding print carries its own `fundingTime` = the moment it became known, so
there is no lookahead: at decision time T we only use prints with fundingTime <= T.
Cached to research/cache/ so we fetch once. Funding settles every 8h (3 prints/day).
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

BASE = "https://fapi.binance.com/fapi/v1/fundingRate"
CACHE = Path(__file__).resolve().parents[2] / "research" / "cache"
PERIODS_PER_YEAR = 3 * 365  # 8h funding => 1095 periods/yr


def _get(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "aitrader/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_funding(symbol: str = "BTCUSDT", years: float = 2.0,
                  use_cache: bool = True) -> pd.DataFrame:
    """Return DataFrame indexed by fundingTime (UTC) with a 'funding' column."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / f"{symbol}_funding.json"
    if use_cache and cache_file.exists():
        rows = json.loads(cache_file.read_text())
    else:
        rows = []
        start = int((time.time() - years * 365 * 86400) * 1000)
        now = int(time.time() * 1000)
        while start < now:
            batch = _get(f"{BASE}?symbol={symbol}&startTime={start}&limit=1000")
            if not batch:
                break
            rows.extend(batch)
            last = batch[-1]["fundingTime"]
            if last <= start:
                break
            start = last + 1
            if len(batch) < 1000:
                break
        cache_file.write_text(json.dumps(rows))

    if not rows:
        raise RuntimeError(f"No funding data for {symbol}")
    df = pd.DataFrame(rows)
    df["funding"] = df["fundingRate"].astype(float)
    df["t"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    return df.set_index("t")[["funding"]].sort_index()
