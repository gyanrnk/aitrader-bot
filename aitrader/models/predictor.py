"""Gradient-boosted classifier that outputs a CALIBRATED probability of an up-move.

Backend preference: LightGBM > sklearn HistGradientBoosting > numpy logistic.
Kept import-lazy with graceful fallback so it runs anywhere.

Returns a probability in [0,1]; the decision graph converts it to a stance
(2*p - 1) with conviction |2*p - 1|. Calibration matters more than raw accuracy:
a well-calibrated 0.55 you can size on beats an over-confident 0.9 you can't trust.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS


def _make_model():
    """Best available gradient booster, else a logistic fallback."""
    try:
        from lightgbm import LGBMClassifier
        return ("lightgbm", LGBMClassifier(
            n_estimators=300, learning_rate=0.03, num_leaves=31,
            subsample=0.8, colsample_bytree=0.8, min_child_samples=30,
            reg_lambda=1.0, verbose=-1))
    except Exception:
        pass
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        return ("sklearn_hgb", HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.03, max_leaf_nodes=31, l2_regularization=1.0))
    except Exception:
        pass
    from ._logistic import NumpyLogistic
    return ("numpy_logistic", NumpyLogistic())


@dataclass
class Predictor:
    backend: str = ""
    model: object = None
    features: list = field(default_factory=lambda: list(FEATURE_COLUMNS))
    mean_: np.ndarray = None
    std_: np.ndarray = None

    # ---- training ----
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "Predictor":
        Xn, self.mean_, self.std_ = _standardize(X[self.features].to_numpy())
        yv = y.to_numpy().astype(int)
        self.backend, self.model = _make_model()
        self.model.fit(Xn, yv)
        return self

    # ---- inference ----
    def predict_proba_up(self, X: pd.DataFrame) -> np.ndarray:
        Xn = (X[self.features].to_numpy() - self.mean_) / self.std_
        Xn = np.nan_to_num(Xn)
        proba = self.model.predict_proba(Xn)
        return proba[:, 1] if proba.ndim == 2 else proba

    def predict_last(self, X: pd.DataFrame) -> float:
        """Probability of up-move for the most recent bar."""
        row = X[self.features].iloc[[-1]]
        return float(self.predict_proba_up(row)[0])

    # ---- persistence ----
    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: str | Path) -> "Predictor":
        with open(path, "rb") as f:
            return pickle.load(f)


def _standardize(X: np.ndarray):
    X = np.nan_to_num(X)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    return (X - mean) / std, mean, std
