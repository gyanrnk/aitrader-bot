"""Walk-forward backtest: replay history through the SAME decision graph, one bar
at a time, enforcing point-in-time visibility and charging costs. Then score it
against baselines and overfit checks.

Same code path as live (graph.run) — no separate "backtest strategy" to drift.
"""
from __future__ import annotations

import pandas as pd

from ..config import Settings
from ..data.indicators import compute_features
from ..discipline.costs import net_returns
from ..discipline.baselines import run_baselines
from ..discipline.firewall import point_in_time_view
from ..discipline.overfit import scorecard
from ..memory import LayeredMemory, reflect_on_trade
from ..orchestration import DecisionGraph
from ..state import TradingState


class Backtester:
    def __init__(self, settings: Settings, use_memory: bool = True):
        self.settings = settings
        self.memory = LayeredMemory(
            recency_factor=settings.memory_recency_factor,
            importance_decay=settings.memory_importance_decay,
        ) if use_memory else None
        self.graph = DecisionGraph(settings, memory=self.memory)

    def run(self, symbol: str, ohlcv: pd.DataFrame, warmup: int = 60, step: int = 5) -> dict:
        weights, gross, dates = [], [], []
        prev_weight = 0.0

        for t in range(warmup, len(ohlcv) - 1, step):
            as_of = ohlcv.index[t]
            visible = point_in_time_view(ohlcv, as_of)          # firewall
            state = TradingState(
                symbol=symbol, as_of=str(as_of), ohlcv=visible,
                features=compute_features(visible),
            )
            if self.memory is not None:
                self.memory.step_decay()                        # age memory each cycle
            decision = self.graph.run(state)

            # hold this weight over the next `step` bars; realize the return
            fwd = ohlcv["close"].iloc[t: t + step + 1].pct_change().dropna()
            for r in fwd:
                gross.append(decision.target_weight * r)
                weights.append(decision.target_weight)
                dates.append(as_of)

            # reflection: learn from the realized move
            if self.memory is not None:
                realized = float(ohlcv["close"].iloc[min(t + step, len(ohlcv) - 1)] /
                                 ohlcv["close"].iloc[t] - 1) * (1 if decision.target_weight >= 0 else -1)
                reflect_on_trade(decision, realized * abs(decision.target_weight or 1), self.memory)
            prev_weight = decision.target_weight

        gross_s = pd.Series(gross, index=pd.DatetimeIndex(dates))
        weight_s = pd.Series(weights, index=pd.DatetimeIndex(dates))
        net_s = net_returns(gross_s, weight_s, self.settings.cost_bps_per_side)

        prices = ohlcv["close"].loc[net_s.index[0]:] if len(net_s) else ohlcv["close"]
        baselines = run_baselines(prices, seed=self.settings.seed)
        report = scorecard(net_s, baselines)
        report["symbol"] = symbol
        report["n_periods"] = len(net_s)
        report["net_of_cost"] = True

        # expose curves for the dashboard (equity of strategy vs buy & hold)
        import pandas as _pd
        self.last_net = net_s
        self.last_equity = (1 + net_s.fillna(0)).cumprod()
        self.last_buyhold = (1 + baselines["buy_and_hold"].reindex(net_s.index).fillna(0)).cumprod()
        self.last_curves = _pd.DataFrame(
            {"strategy": self.last_equity, "buy_and_hold": self.last_buyhold})
        return report
