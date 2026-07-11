"""Intelligent signals from the collected data + HONEST forward accuracy tracking.

The honest idea: a signal is worthless until measured on data it has never seen. So we
(1) compute a transparent signal from each snapshot, (2) log the prediction, and
(3) later — once real time has passed — score it against what the market actually did.
The accuracy you see here is FORWARD-measured, not a backtest that can be curve-fit.

Signal basis (research-grounded, NOT a magic predictor):
  * funding z-score  -> contrarian: crowded longs (high +funding) = pullback risk
  * open-interest chg -> rising OI + move = fresh positioning (fragility)
  * short momentum    -> trend persistence
Expect realistic ~50-55% directional hit-rate at best. Higher early = too little data.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "data" / "market"
PRED_FILE = ROOT / "data" / "predictions.csv"
PRED_COLS = ["ts", "symbol", "price", "prob_up", "signal", "score"]


def load_history() -> pd.DataFrame:
    files = sorted(STORE.glob("*.csv"))
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.sort_values("ts")


def compute_signal(sym_df: pd.DataFrame, win: int = 12, k: int = 4) -> dict | None:
    """Latest signal for one symbol's time-ordered snapshots."""
    if len(sym_df) < max(win, k) + 1:
        return None                                   # not enough history yet
    funding = sym_df["funding"].astype(float)
    price = sym_df["price"].astype(float)
    oi = sym_df["open_interest"].astype(float)

    f_mean, f_std = funding.tail(win).mean(), funding.tail(win).std(ddof=0)
    f_z = (funding.iloc[-1] - f_mean) / f_std if f_std > 0 else 0.0
    oi_chg = oi.iloc[-1] / oi.iloc[-k] - 1 if oi.iloc[-k] else 0.0
    mom = price.iloc[-1] / price.iloc[-k] - 1

    # transparent, bounded score. Contrarian on funding extreme + small momentum tilt.
    score = (-0.6 * float(np.clip(f_z / 2.0, -1, 1))
             + 0.3 * float(np.tanh(mom * 20))
             - 0.2 * float(np.tanh(oi_chg * 5)) * float(np.sign(mom)))
    prob_up = 1.0 / (1.0 + math.exp(-2.0 * score))
    signal = "UP" if prob_up > 0.55 else "DOWN" if prob_up < 0.45 else "FLAT"
    return {"price": float(price.iloc[-1]), "funding_z": round(f_z, 2),
            "oi_chg": round(oi_chg, 4), "mom": round(mom, 4),
            "prob_up": round(prob_up, 3), "signal": signal, "score": round(score, 3)}


def log_predictions(history: pd.DataFrame) -> list[dict]:
    """Compute + append the latest prediction per symbol to predictions.csv."""
    if history.empty:
        return []
    ts = history["ts"].max()
    rows = []
    for sym, g in history.groupby("symbol"):
        sig = compute_signal(g)
        if sig and sig["signal"] != "FLAT":
            rows.append({"ts": ts.isoformat(), "symbol": sym, "price": sig["price"],
                         "prob_up": sig["prob_up"], "signal": sig["signal"], "score": sig["score"]})
    if rows:
        new = pd.DataFrame(rows)
        if PRED_FILE.exists():
            new.to_csv(PRED_FILE, mode="a", header=False, index=False)
        else:
            new.to_csv(PRED_FILE, index=False)
    return rows


def score_predictions(history: pd.DataFrame, horizon_hours: float = 8.0) -> dict:
    """Score MATURED predictions (>= horizon old) against realized price moves.
    This is the honest forward accuracy: hit-rate AND expectancy (net direction return).
    """
    if not PRED_FILE.exists() or history.empty:
        return {"scored": 0, "note": "no matured predictions yet — accuracy builds over time"}
    preds = pd.read_csv(PRED_FILE)
    preds["ts"] = pd.to_datetime(preds["ts"], utc=True)
    horizon = pd.Timedelta(hours=horizon_hours)
    now = history["ts"].max()

    hits, rets = [], []
    for _, p in preds.iterrows():
        if now - p["ts"] < horizon:
            continue                                  # not matured yet
        later = history[(history["symbol"] == p["symbol"]) &
                        (history["ts"] >= p["ts"] + horizon)]
        if later.empty:
            continue
        px_then = float(p["price"]); px_later = float(later.iloc[0]["price"])
        realized = px_later / px_then - 1
        direction = 1 if p["signal"] == "UP" else -1
        hits.append(1 if direction * realized > 0 else 0)
        rets.append(direction * realized)            # return if you traded the signal
    if not hits:
        return {"scored": 0, "note": "predictions logged but none matured yet"}
    rets = np.array(rets)
    return {
        "scored": len(hits),
        "hit_rate": round(float(np.mean(hits)), 3),          # directional accuracy
        "avg_return_per_call": round(float(rets.mean()), 5),  # expectancy (the real metric)
        "expectancy_positive": bool(rets.mean() > 0),
        "horizon_hours": horizon_hours,
    }
