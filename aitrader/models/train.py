"""Train + honestly evaluate the predictor.

Reports BOTH:
  * accuracy / AUC per purged walk-forward fold (the ML view), and
  * net-of-cost economic metrics of trading on the probability (the money view).

Accuracy that doesn't turn into net-of-cost edge is worthless — we print both so you
can't confuse the two. Saves the final model (fit on all data) to `models_store/`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..discipline.costs import net_returns
from ..discipline.overfit import sharpe, max_drawdown
from .features import build_features, FEATURE_COLUMNS
from .labeling import triple_barrier_labels
from .predictor import Predictor
from .validation import purged_walk_forward_splits


def _prep(ohlcv: pd.DataFrame, horizon: int, extra: pd.DataFrame | None = None):
    X = build_features(ohlcv)
    cols = list(FEATURE_COLUMNS)
    if extra is not None:
        X = X.join(extra)                       # align on date index
        cols += [c for c in extra.columns if c not in cols]
    y = triple_barrier_labels(ohlcv["close"], horizon=horizon)
    data = X.join(y.rename("label")).dropna()
    return data[cols], data["label"].astype(int), ohlcv["close"].loc[data.index], cols


def train_and_eval(
    ohlcv: pd.DataFrame,
    horizon: int = 5,
    n_splits: int = 5,
    cost_bps: float = 5.0,
    prob_threshold: float = 0.55,
    save_path: str | Path | None = None,
    extra: pd.DataFrame | None = None,
) -> tuple[dict, "Predictor"]:
    X, y, close, cols = _prep(ohlcv, horizon, extra)
    n = len(X)
    fold_acc, fold_auc, oos_rets, oos_w = [], [], [], []

    for train_idx, test_idx in purged_walk_forward_splits(n, n_splits=n_splits, embargo=horizon):
        model = Predictor(features=cols).fit(X.iloc[train_idx], y.iloc[train_idx])
        p = model.predict_proba_up(X.iloc[test_idx])
        yt = y.iloc[test_idx].to_numpy()

        pred = (p >= 0.5).astype(int)
        fold_acc.append(float((pred == yt).mean()))
        fold_auc.append(_auc(yt, p))

        # translate probability -> position, realize next-bar return, net of cost
        fwd = close.iloc[test_idx].pct_change().shift(-1).fillna(0).to_numpy()
        weight = np.where(p >= prob_threshold, 1.0, np.where(p <= 1 - prob_threshold, -1.0, 0.0))
        oos_rets.append(pd.Series(weight * fwd, index=X.index[test_idx]))
        oos_w.append(pd.Series(weight, index=X.index[test_idx]))

    gross = pd.concat(oos_rets) if oos_rets else pd.Series(dtype=float)
    weights = pd.concat(oos_w) if oos_w else pd.Series(dtype=float)
    net = net_returns(gross, weights, cost_bps) if len(gross) else gross

    # final model on ALL data for live use
    final = Predictor(features=cols).fit(X, y)
    report = {
        "n_samples": int(n),
        "backend": final.backend,
        "n_features": len(cols),
        "cv_accuracy_mean": round(float(np.mean(fold_acc)), 4) if fold_acc else None,
        "cv_auc_mean": round(float(np.nanmean(fold_auc)), 4) if fold_auc else None,
        "oos_net_sharpe": round(sharpe(net), 3) if len(net) else None,
        "oos_net_total_return": round(float((1 + net.fillna(0)).prod() - 1), 4) if len(net) else None,
        "oos_max_drawdown": round(max_drawdown(net), 4) if len(net) else None,
        "label_balance": round(float(y.mean()), 3),
    }
    if save_path:
        final.save(save_path)
        report["saved_to"] = str(save_path)
    return report, final


def train_and_eval_meta(
    ohlcv: pd.DataFrame,
    horizon: int = 5,
    n_splits: int = 5,
    cost_bps: float = 5.0,
    meta_threshold: float = 0.55,
) -> tuple[dict, None]:
    """Same scoreboard shape as train_and_eval, but trades the META-FILTERED primary."""
    from .meta_labeling import meta_walk_forward

    X, y, close, _cols = _prep(ohlcv, horizon)
    n = len(X)
    splits = list(purged_walk_forward_splits(n, n_splits=n_splits, embargo=horizon))
    net, weights, m = meta_walk_forward(
        X, y, close, splits, cost_bps=cost_bps, meta_threshold=meta_threshold)

    report = {
        "n_samples": int(n),
        "backend": "meta+" + (Predictor().fit(X.iloc[: max(50, n // 2)],
                                               y.iloc[: max(50, n // 2)]).backend),
        # keep the shared keys so evaluate.py can print/log uniformly:
        "cv_accuracy_mean": m["meta_trade_accuracy"],   # accuracy ON TRADES TAKEN
        "cv_auc_mean": m["primary_accuracy"],           # primary directional accuracy
        "oos_net_sharpe": round(sharpe(net), 3) if len(net) else None,
        "oos_net_total_return": round(float((1 + net.fillna(0)).prod() - 1), 4) if len(net) else None,
        "oos_max_drawdown": round(max_drawdown(net), 4) if len(net) else None,
        "trade_fraction": m["trade_fraction"],
        "label_balance": round(float(y.mean()), 3),
    }
    return report, None


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    """ROC-AUC without sklearn: probability a random pos ranks above a random neg."""
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(p)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(p) + 1)
    return float((ranks[y == 1].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))
