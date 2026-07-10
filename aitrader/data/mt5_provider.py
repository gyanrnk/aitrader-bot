"""Forex/CFD market data via MetaTrader 5. LOCAL Windows only.

Requires: the MT5 desktop terminal installed + logged into a broker account (demo is
fine) and `pip install MetaTrader5`. Lazy-imported so the rest of the app (and cloud
deploy) never depends on it. Returns the same normalized OHLCV frame as other providers.

Note: in forex/CFD you trade against the BROKER's price feed (spreads + swaps), not a
central exchange — and there is no funding-carry edge here (that's crypto-specific).
"""
from __future__ import annotations

import pandas as pd

from ..config import Settings


class MT5Provider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _init(self, mt5):
        s = self.settings
        ok = mt5.initialize(login=s.mt5_login, password=s.mt5_password, server=s.mt5_server) \
            if s.mt5_login else mt5.initialize()
        if not ok:
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}. "
                               "Terminal chalu hai? Login sahi hai? (see FOREX_MT5.md)")

    def ohlcv(self, symbol: str, lookback: int = 400) -> pd.DataFrame:
        try:
            import MetaTrader5 as mt5  # Windows-only, lazy
        except Exception as e:
            raise RuntimeError("MetaTrader5 package missing. Run: pip install MetaTrader5 "
                               "(Windows only). See FOREX_MT5.md.") from e

        self._init(mt5)
        tf_map = {"D1": mt5.TIMEFRAME_D1, "H4": mt5.TIMEFRAME_H4,
                  "H1": mt5.TIMEFRAME_H1, "M15": mt5.TIMEFRAME_M15}
        tf = tf_map.get(self.settings.mt5_timeframe, mt5.TIMEFRAME_D1)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, lookback)
        mt5.shutdown()
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"MT5 returned no data for {symbol!r}. Symbol Market Watch me hai?")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.set_index("time").rename(columns={"tick_volume": "volume"})
        return df[["open", "high", "low", "close", "volume"]].tail(lookback)
