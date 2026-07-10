"""Layered memory store + retrieval ranking.

Retrieval score (FinMem `compound_score.py`):
    recency_and_importance = recency + importance / 100
    merge_score            = similarity + recency_and_importance

Layers (FinMem `importance_score.py`): short / mid / long / reflection carry
different importance priors so tactical noise fades fast and deep lessons persist.

Embeddings: mock mode uses a deterministic hashing embedding (no network). Point
`embed_fn` at a real embedding model (Anthropic/Voyage/OpenAI) for production.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from .decay import exponential_decay

Layer = str  # "short" | "mid" | "long" | "reflection"

_IMPORTANCE_PRIOR = {"short": 55.0, "mid": 60.0, "long": 75.0, "reflection": 80.0}


@dataclass
class MemoryItem:
    text: str
    layer: Layer
    vec: np.ndarray
    importance: float
    recency: float = 1.0
    delta: float = 0.0
    ts: float = field(default_factory=time.time)
    access_count: int = 0


def _hash_embed(text: str, dim: int = 128) -> np.ndarray:
    """Deterministic bag-of-hashed-tokens embedding. Good enough for mock retrieval."""
    v = np.zeros(dim, dtype=np.float64)
    for tok in text.lower().split():
        v[hash(tok) % dim] += 1.0
    n = np.linalg.norm(v)
    return v / n if n else v


class LayeredMemory:
    def __init__(
        self,
        recency_factor: float = 10.0,
        importance_decay: float = 0.988,
        embed_fn: Optional[Callable[[str], np.ndarray]] = None,
    ):
        self.recency_factor = recency_factor
        self.importance_decay = importance_decay
        self.embed_fn = embed_fn or _hash_embed
        self.items: list[MemoryItem] = []

    def add(self, text: str, layer: Layer = "mid", importance: Optional[float] = None):
        imp = importance if importance is not None else _IMPORTANCE_PRIOR.get(layer, 60.0)
        self.items.append(
            MemoryItem(text=text, layer=layer, vec=self.embed_fn(text), importance=imp)
        )

    def step_decay(self) -> None:
        """Age every memory one tick. Call once per decision cycle."""
        for it in self.items:
            it.recency, it.importance, it.delta = exponential_decay(
                it.importance, it.delta, self.recency_factor, self.importance_decay
            )

    def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        """Rank by similarity + recency + importance/100 (FinMem merge_score)."""
        if not self.items:
            return []
        q = self.embed_fn(query)
        scored: list[tuple[float, MemoryItem]] = []
        for it in self.items:
            similarity = float(np.dot(q, it.vec))
            recency_and_importance = it.recency + min(it.importance, 100) / 100.0
            merge = similarity + recency_and_importance
            scored.append((merge, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [it for _, it in scored[:top_k]]
        for it in top:                       # reinforce what gets used
            it.access_count += 1
            it.importance = min(it.importance + 1.0, 100.0)
        return top
