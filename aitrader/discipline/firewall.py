"""Leakage firewall / point-in-time guard.

The single most important correctness check in any backtest: at decision time T the
agent may ONLY see data with timestamp <= T. This raises if a caller ever hands a
frame that extends past the decision timestamp (agent-backtest-lab `data/firewall.py`).
"""
from __future__ import annotations

import pandas as pd


class LookaheadError(AssertionError):
    pass


def assert_point_in_time(df: pd.DataFrame, as_of) -> pd.DataFrame:
    """Return the slice of `df` visible at `as_of`; raise if it can't be enforced."""
    as_of = pd.Timestamp(as_of)
    if df.index.max() > as_of:
        # Caller passed future rows — slice them off AND warn loudly.
        visible = df.loc[df.index <= as_of]
        if visible.empty:
            raise LookaheadError(f"No data available at or before {as_of}.")
        return visible
    return df


def point_in_time_view(df: pd.DataFrame, as_of) -> pd.DataFrame:
    """Non-raising helper: strictly the rows knowable at `as_of`."""
    return df.loc[df.index <= pd.Timestamp(as_of)]
