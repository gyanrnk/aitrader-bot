"""Smoke tests: the whole architecture runs end-to-end in mock mode."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from aitrader.config import Settings
from aitrader.data import get_provider
from aitrader.data.indicators import compute_features
from aitrader.discipline.firewall import point_in_time_view, assert_point_in_time, LookaheadError
from aitrader.discipline.overfit import sharpe, detect_reward_hacking
from aitrader.memory import LayeredMemory
from aitrader.runner import TradingBot
from aitrader.backtest import Backtester


def test_end_to_end_decision():
    bot = TradingBot(Settings(mode="mock", data_provider="mock"))
    decision, state = bot.decide("MOCKX")
    assert decision.symbol == "MOCKX"
    assert -1.0 <= decision.target_weight <= 1.0
    assert len(state.reports) == 4          # four analysts ran
    assert state.risk_decision is not None


def test_position_within_caps():
    s = Settings(mode="mock", max_position_pct=0.2)
    bot = TradingBot(s)
    decision, _ = bot.decide("MOCKX")
    assert abs(decision.target_weight) <= s.max_position_pct + 1e-9


def test_memory_decay_and_retrieval():
    m = LayeredMemory()
    m.add("shorted into earnings and lost", layer="reflection", importance=90)
    m.add("bought oversold bounce and won", layer="mid", importance=60)
    before = m.items[0].recency
    m.step_decay()
    assert m.items[0].recency < before      # recency decays
    hits = m.retrieve("earnings short setup", top_k=1)
    assert hits and "earnings" in hits[0].text


def test_firewall_blocks_lookahead():
    prov = get_provider(Settings(data_provider="mock"))
    df = prov.ohlcv("MOCKX", lookback=100)
    as_of = df.index[50]
    visible = point_in_time_view(df, as_of)
    assert visible.index.max() <= as_of
    # assert_point_in_time trims future rows rather than leaking them
    trimmed = assert_point_in_time(df, as_of)
    assert trimmed.index.max() <= as_of


def test_backtest_scorecard_is_net_of_cost():
    s = Settings(mode="mock")
    df = get_provider(s).ohlcv("MOCKX", lookback=300)
    report = Backtester(s).run("MOCKX", df, warmup=60, step=5)
    assert report["net_of_cost"] is True
    assert "beats_buy_and_hold" in report
    assert "overfit_flags" in report


def test_sharpe_and_overfit_helpers():
    good = pd.Series([0.01, 0.02, -0.005, 0.015] * 30)
    assert sharpe(good) != 0
    flags = detect_reward_hacking(good)
    assert isinstance(flags, list) and flags


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
    print("all smoke tests passed")
