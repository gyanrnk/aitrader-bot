"""Dependency-free logistic-regression fallback (numpy only).

Guarantees the ML layer runs even with no sklearn/lightgbm installed. Not as strong
as gradient boosting, but keeps the architecture importable and testable anywhere.
"""
from __future__ import annotations

import numpy as np


class NumpyLogistic:
    def __init__(self, lr: float = 0.1, epochs: int = 400, l2: float = 1e-3):
        self.lr, self.epochs, self.l2 = lr, epochs, l2
        self.w = None
        self.b = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray):
        X = np.nan_to_num(X)
        n, d = X.shape
        self.w = np.zeros(d)
        for _ in range(self.epochs):
            z = X @ self.w + self.b
            p = 1 / (1 + np.exp(-z))
            grad_w = X.T @ (p - y) / n + self.l2 * self.w
            grad_b = float((p - y).mean())
            self.w -= self.lr * grad_w
            self.b -= self.lr * grad_b
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        X = np.nan_to_num(X)
        p = 1 / (1 + np.exp(-(X @ self.w + self.b)))
        return np.column_stack([1 - p, p])
