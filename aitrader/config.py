"""Central configuration. One place for every knob; read from env with safe defaults.

Mirrors TradingAgents' `default_config.py` idea: a single settings object threaded
through the whole system so no module hard-codes a key, model, or risk limit.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Any


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # --- run mode ---
    mode: str = os.getenv("AITRADER_MODE", "mock")            # mock | live
    data_provider: str = os.getenv("AITRADER_DATA_PROVIDER", "mock")  # mock | yfinance | mt5
    broker: str = os.getenv("AITRADER_BROKER", "paper")       # paper | ccxt | mt5

    # --- MT5 (forex/CFD) — LOCAL Windows only: needs MT5 terminal + broker demo login ---
    mt5_login: int = _i("MT5_LOGIN", 0)
    mt5_password: str = os.getenv("MT5_PASSWORD", "")
    mt5_server: str = os.getenv("MT5_SERVER", "")
    mt5_timeframe: str = os.getenv("AITRADER_MT5_TIMEFRAME", "D1")   # D1 | H1 | H4 | M15

    # --- llm ---
    # backend for the (optional) reasoning layer:
    #   quant  = no LLM at all, pure deterministic signals  (FREE, default, hot-path)
    #   groq   = Groq API (free tier, OpenAI-compatible)     (FREE/cheap, slow-loop)
    #   claude = Anthropic API                               (PAID, slow-loop only)
    llm_backend: str = os.getenv("AITRADER_LLM_BACKEND", "quant")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    llm_model: str = os.getenv("AITRADER_LLM_MODEL", "claude-sonnet-5")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("AITRADER_GROQ_MODEL", "llama-3.3-70b-versatile")
    # If False, the LLM never runs in the per-bar decision (keeps trading free/fast).
    # The LLM is then used only by the slow loop (regime/news/reflection).
    use_llm_in_decision: bool = os.getenv("AITRADER_USE_LLM_IN_DECISION", "0") == "1"

    # --- decision graph ---
    max_debate_rounds: int = _i("AITRADER_MAX_DEBATE_ROUNDS", 1)
    max_risk_rounds: int = _i("AITRADER_MAX_RISK_ROUNDS", 1)
    analysts: tuple = ("market", "news", "sentiment", "fundamentals")

    # --- risk limits ---
    max_position_pct: float = _f("AITRADER_MAX_POSITION_PCT", 0.20)
    risk_per_trade_pct: float = _f("AITRADER_RISK_PER_TRADE_PCT", 0.01)
    max_gross_exposure: float = _f("AITRADER_MAX_GROSS_EXPOSURE", 1.0)

    # --- costs (net-of-cost is non-negotiable; see discipline/costs.py) ---
    cost_bps_per_side: float = _f("AITRADER_COST_BPS_PER_SIDE", 5.0)

    # --- memory ---
    memory_recency_factor: float = _f("AITRADER_MEM_RECENCY", 10.0)
    memory_importance_decay: float = _f("AITRADER_MEM_IMPORTANCE_DECAY", 0.988)
    memory_top_k: int = _i("AITRADER_MEM_TOP_K", 5)

    # --- misc ---
    starting_equity: float = _f("AITRADER_STARTING_EQUITY", 100_000.0)
    seed: int = _i("AITRADER_SEED", 42)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_settings() -> Settings:
    """Load settings, applying a local .env if python-dotenv is available."""
    try:  # optional convenience; not required
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        pass
    return Settings()
