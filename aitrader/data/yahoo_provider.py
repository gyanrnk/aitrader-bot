"""Real market data with ZERO dependencies — Yahoo's chart API over stdlib urllib.

WHY THIS EXISTS: the dashboard defaulted to `mock` (a random walk) and rendered BTC-USD at
$101.98 under a heading reading "Markets", while BTC was $63,227. Every downstream tab then
reasoned about fake numbers, and a user trying to learn from it could not possibly succeed.

The obvious fix — default to the `yfinance` provider — does NOT work where it matters.
`yfinance` is commented out of requirements.txt because its dependency tree broke the
Streamlit Cloud build (commit 836d99f). So on the DEPLOYED app, the "real data" option
isn't installed and mock is all there is. Fixing the default locally would have changed
nothing on the URL the user actually opens.

But we never needed the package. `aitrader/collector/snapshot.py` has been pulling real
Yahoo prices with plain urllib this whole time — the same chart endpoint also returns full
OHLCV history:

    GET https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?range=1y&interval=1d
    -> 366 daily bars, open/high/low/close/volume

Verified 2026-07-17: BTC-USD $63,213.71, AAPL, ^NSEI (Nifty), GC=F (gold) all return data.
stdlib only, so it installs anywhere `streamlit` does — including Streamlit Cloud.

`yfinance` remains available as an explicit choice (it does adjust for splits/dividends,
which this does not — see `auto_adjust` in yfinance_provider.py). For crypto and index
levels that distinction is irrelevant; for individual equities over long windows it is not.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

import pandas as pd

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{}?range={}&interval=1d"

# Yahoo only accepts a fixed set of range tokens — pick the smallest that covers `lookback`
# trading days. Stocks trade ~252 days/yr, so ask for calendar slack, then tail().
_RANGES = [(20, "1mo"), (60, "3mo"), (120, "6mo"), (250, "1y"),
           (500, "2y"), (1200, "5y"), (10**9, "max")]


def _range_for(lookback: int) -> str:
    for limit, token in _RANGES:
        if lookback <= limit:
            return token
    return "max"


class YahooProvider:
    """Normalized OHLCV, indexed by datetime. No third-party packages."""

    def ohlcv(self, symbol: str, lookback: int = 400) -> pd.DataFrame:
        url = CHART.format(urllib.parse.quote(symbol), _range_for(lookback))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read())

        result = (payload.get("chart") or {}).get("result")
        if not result:
            err = ((payload.get("chart") or {}).get("error") or {}).get("description", "")
            raise RuntimeError(f"Yahoo returned no data for {symbol!r}. {err}".strip())

        res = result[0]
        quote = res["indicators"]["quote"][0]
        df = pd.DataFrame({
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "close": quote.get("close"),
            "volume": quote.get("volume"),
        }, index=pd.to_datetime(res["timestamp"], unit="s", utc=True))

        # Yahoo emits null bars for holidays/halts — drop rows with no close, then
        # forward-fill the rest so a single missing high/low can't poison a whole window.
        df = df.dropna(subset=["close"]).ffill()
        if df.empty:
            raise RuntimeError(f"Yahoo returned only empty bars for {symbol!r}")
        df["volume"] = df["volume"].fillna(0.0)
        return df.tail(lookback)
