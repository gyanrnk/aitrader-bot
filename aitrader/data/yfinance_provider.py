"""Live market data via yfinance. Optional — only imported when selected."""
from __future__ import annotations

import pandas as pd


class YFinanceProvider:
    def ohlcv(self, symbol: str, lookback: int = 400) -> pd.DataFrame:
        import yfinance as yf  # local import so core has no hard dep

        # request extra calendar days to net `lookback` trading rows
        period_days = int(lookback * 1.6) + 10
        df = yf.download(
            symbol,
            period=f"{period_days}d",
            interval="1d",
            auto_adjust=True,      # adjust for splits/dividends (corporate actions)
            progress=False,
        )
        if df.empty:
            raise RuntimeError(f"yfinance returned no data for {symbol!r}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        return df.tail(lookback)
