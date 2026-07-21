"""Pluggable strategies. One interface, two shapes — see `base.py`."""
from .base import Action, MechanismStudy, Signal, Strategy
from .classic import REGISTRY, MACrossover, RSIReversion

__all__ = ["Action", "MechanismStudy", "Signal", "Strategy",
           "MACrossover", "RSIReversion", "REGISTRY"]
