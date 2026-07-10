"""One interface, many sources. Swap data vendors without touching agent code.

This is the seam TradingAgents uses in `dataflows/interface.py`: every provider
returns a normalized OHLCV frame indexed by timestamp with columns
[open, high, low, close, volume].
"""
from __future__ import annotations

from typing import Protocol

import pandas as pd

from ..config import Settings


class DataProvider(Protocol):
    def ohlcv(self, symbol: str, lookback: int = 400) -> pd.DataFrame:
        """Return a DataFrame indexed by datetime with open/high/low/close/volume."""
        ...


def get_provider(settings: Settings) -> DataProvider:
    """Factory: choose provider from settings. Falls back to mock."""
    name = settings.data_provider.lower()
    if name == "yfinance":
        from .yfinance_provider import YFinanceProvider
        return YFinanceProvider()
    if name == "mt5":
        from .mt5_provider import MT5Provider
        return MT5Provider(settings)
    from .mock_provider import MockProvider
    return MockProvider(seed=settings.seed)
