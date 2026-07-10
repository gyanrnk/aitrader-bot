"""Meta-labeling (López de Prado): a second model decides WHETHER to act.

Two stages, leakage-safe:
  * PRIMARY model predicts the side (up/down).
  * META model predicts P(primary is correct) and we trade only when that is high,
    sizing the bet by the meta-probability.

Why it helps: the primary can have poor accuracy but the meta filter raises PRECISION
on the trades you actually take, and turns "always in the market" into "in only when
the odds are good" — which is usually what flips a near-zero strategy positive.

Leakage guard: within each walk-forward train window we split again (inner a/b). The
primary is fit on `a`, its predictions on `b` generate the meta-labels — so the meta
model never sees the primary's in-sample overconfidence.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .predictor import _make_model, _standardize


def _fit(Xnp: np.ndarray, y: np.ndarray):
    Xn, mean, std = _standardize(Xnp)
    backend, model = _make_model()
    model.fit(Xn, y.astype(int))
    return (backend, model, mean, std)


def _proba(bundle, Xnp: np.ndarray) -> np.ndarray:
    _, model, mean, std = bundle
    Xn = np.nan_to_num((Xnp - mean) / std)
    p = model.predict_proba(Xn)
    return p[:, 1] if (p.ndim == 2 and p.shape[1] == 2) else np.full(len(Xnp), 0.5)


def meta_walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    close: pd.Series,
    splits,
    cost_bps: float = 5.0,
    meta_threshold: float = 0.55,
    inner_frac: float = 0.7,
):
    """Return (net_returns, weights, metrics) trading the meta-filtered primary."""
    feat = X.to_numpy()
    yv = y.to_numpy().astype(int)
    prim_acc, meta_acc, trade_frac = [], [], []
    oos_rets, oos_w = [], []

    for tr, te in splits:
        # --- inner split to build meta-labels without leakage ---
        cut = int(len(tr) * inner_frac)
        a, b = tr[:cut], tr[cut:]
        if len(a) < 30 or len(b) < 20:
            continue
        primary_a = _fit(feat[a], yv[a])
        p_b = _proba(primary_a, feat[b])
        side_b = (p_b >= 0.5).astype(int)
        meta_y = (side_b == yv[b]).astype(int)        # was the primary right?
        if len(np.unique(meta_y)) < 2:
            continue
        meta_X_b = np.column_stack([feat[b], p_b, np.abs(p_b - 0.5)])
        meta_model = _fit(meta_X_b, meta_y)

        # --- test: primary on full train window, meta filter on top ---
        primary_full = _fit(feat[tr], yv[tr])
        p_te = _proba(primary_full, feat[te])
        side_te = (p_te >= 0.5).astype(int)
        meta_X_te = np.column_stack([feat[te], p_te, np.abs(p_te - 0.5)])
        meta_prob = _proba(meta_model, meta_X_te)

        take = meta_prob >= meta_threshold
        signed = np.where(side_te == 1, 1.0, -1.0) * take     # +1/-1/0
        weight = signed * meta_prob                            # size by confidence

        fwd = close.iloc[te].pct_change().shift(-1).fillna(0).to_numpy()
        idx = X.index[te]
        oos_rets.append(pd.Series(weight * fwd, index=idx))
        oos_w.append(pd.Series(weight, index=idx))

        prim_acc.append(float((side_te == yv[te]).mean()))
        if take.sum() > 0:
            meta_acc.append(float((side_te == yv[te])[take].mean()))
            trade_frac.append(float(take.mean()))

    from ..discipline.costs import net_returns
    gross = pd.concat(oos_rets) if oos_rets else pd.Series(dtype=float)
    weights = pd.concat(oos_w) if oos_w else pd.Series(dtype=float)
    net = net_returns(gross, weights, cost_bps) if len(gross) else gross
    metrics = {
        "primary_accuracy": round(float(np.mean(prim_acc)), 4) if prim_acc else None,
        "meta_trade_accuracy": round(float(np.mean(meta_acc)), 4) if meta_acc else None,
        "trade_fraction": round(float(np.mean(trade_frac)), 3) if trade_frac else 0.0,
    }
    return net, weights, metrics
