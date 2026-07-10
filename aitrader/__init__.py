"""aitrader — a debate-driven, memory-backed, discipline-gated AI trading bot.

Architecture in three signature layers (see ARCHITECTURE.md):
    1. orchestration/  — multi-agent decision graph (analysts -> bull/bear debate
                         -> trader -> risk debate -> portfolio manager)
    2. memory/         — layered memory with exponential decay + reflection
    3. discipline/     — net-of-cost P&L, leakage firewall, baselines, overfit checks

Everything runs end-to-end in `mock` mode with no API keys.
"""

__version__ = "0.1.0"
