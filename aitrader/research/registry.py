"""Hypothesis registry — the append-only log of every edge idea we test.

Enforces the two disciplines that make later numbers trustworthy:
  1. No hypothesis without an economic rationale (who pays me and why).
  2. Every test — pass or fail — is counted, so total trials feed the deflated Sharpe.

Persisted as research/hypotheses.json so it survives across sessions and is the single
source of truth for "how many things did we try?".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "research" / "hypotheses.json"


@dataclass
class Hypothesis:
    id: str
    name: str
    family: str                       # e.g. funding_carry, basis, liq_meanrev, vol_momo
    economic_rationale: str           # WHO pays me and WHY — required, non-empty
    status: str = "proposed"          # proposed | tested | passed | failed
    tests: list = field(default_factory=list)   # each: {stamp, params, is_sharpe, oos_sharpe, note}
    best_oos_sharpe: Optional[float] = None
    notes: str = ""


class HypothesisRegistry:
    def __init__(self, path: Path | str = DEFAULT_PATH):
        self.path = Path(path)
        self.items: dict[str, Hypothesis] = {}
        self._load()

    # ---- persistence ----
    def _load(self) -> None:
        if self.path.exists():
            raw = json.loads(self.path.read_text() or "{}")
            self.items = {k: Hypothesis(**v) for k, v in raw.items()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({k: asdict(v) for k, v in self.items.items()},
                                        indent=2))

    # ---- core ops ----
    def add(self, id: str, name: str, family: str, economic_rationale: str,
            notes: str = "") -> Hypothesis:
        if not economic_rationale.strip():
            raise ValueError("Economic rationale required — 'who pays me and why?'. "
                             "No backtest without it.")
        if id in self.items:
            return self.items[id]
        h = Hypothesis(id=id, name=name, family=family,
                       economic_rationale=economic_rationale.strip(), notes=notes)
        self.items[id] = h
        self.save()
        return h

    def log_test(self, id: str, stamp: str, params: dict,
                 is_sharpe: float, oos_sharpe: float | None = None,
                 note: str = "") -> None:
        """Record ONE backtest attempt (pass or fail). This counts as a trial."""
        h = self.items[id]
        h.tests.append({"stamp": stamp, "params": params,
                        "is_sharpe": round(is_sharpe, 3),
                        "oos_sharpe": None if oos_sharpe is None else round(oos_sharpe, 3),
                        "note": note})
        if oos_sharpe is not None:
            h.best_oos_sharpe = max(h.best_oos_sharpe or -9, round(oos_sharpe, 3))
        h.status = "tested"
        self.save()

    # ---- multiple-testing accounting ----
    def total_trials(self) -> int:
        """Total backtest attempts across ALL hypotheses — the N for deflated Sharpe."""
        return sum(len(h.tests) for h in self.items.values())

    def summary(self) -> dict:
        return {
            "hypotheses": len(self.items),
            "total_trials": self.total_trials(),
            "by_status": {s: sum(1 for h in self.items.values() if h.status == s)
                          for s in ("proposed", "tested", "passed", "failed")},
        }
