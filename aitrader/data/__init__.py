"""Data layer: pluggable providers behind one interface (TradingAgents dataflows pattern)."""
from .interface import DataProvider, get_provider

__all__ = ["DataProvider", "get_provider"]
