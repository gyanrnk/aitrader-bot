"""Reasoning backends behind one interface. Free by default.

Three interchangeable backends (same call sites, chosen by settings.llm_backend):
  * QuantEngine  — NO LLM. Deterministic signal rules. FREE, instant, the default
                   brain that actually trades on the per-bar hot path.
  * GroqLLM      — Groq API (free tier, OpenAI-compatible). FREE/cheap. For the slow
                   loop only (regime read, news, reflection) — never per bar.
  * ClaudeLLM    — Anthropic API. PAID. Top-tier reasoning for the slow loop.

Design rule for profit: the LLM stays OFF the per-bar trading loop unless you opt in
(AITRADER_USE_LLM_IN_DECISION=1). API cost must never be able to exceed edge.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Protocol


class LLM(Protocol):
    def analyze(self, role: str, prompt: str, features: dict) -> dict[str, Any]: ...
    def argue(self, side: str, prompt: str) -> str: ...
    def reflect(self, base: str) -> str: ...


class QuantEngine:
    """FREE deterministic signal engine. No network, no keys, no per-decision cost.

    This is the real hot-path brain: it turns indicators into an analyst stance with
    an explicit, auditable rule per role. Tune these rules — this is where edge lives,
    not in an LLM prompt."""

    def analyze(self, role: str, prompt: str, features: dict) -> dict[str, Any]:
        rsi = features.get("rsi14", 50.0)
        macd_hist = features.get("macd_hist", 0.0)
        trend = features.get("trend", 0.0)
        # each analyst weights features differently
        if role == "market":
            stance = 0.5 * _sign(macd_hist) + 0.5 * _clip(trend * 5)
        elif role == "sentiment":
            stance = _clip((50 - rsi) / 50)         # contrarian on RSI extremes
        elif role == "news":
            stance = _clip(trend * 4)
        else:  # fundamentals
            stance = _clip(trend * 2 + (0.2 if features.get("sma20", 0) > features.get("sma50", 0) else -0.2))
        conf = min(1.0, 0.4 + abs(stance) * 0.6)
        summary = f"{role}: RSI={rsi:.0f}, MACDhist={macd_hist:+.3f}, trend={trend:+.2%} -> stance {stance:+.2f}"
        return {"stance": _clip(stance), "confidence": conf, "summary": summary,
                "evidence": [f"rsi14={rsi:.1f}", f"trend={trend:+.2%}"]}

    def argue(self, side: str, prompt: str) -> str:
        return f"[{side}] {prompt[:160]}"

    def reflect(self, base: str) -> str:
        return f"Lesson: {base}"


def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        return {"stance": 0.0, "confidence": 0.3, "summary": raw[:200], "evidence": []}


class GroqLLM:
    """Groq API client (free tier). OpenAI-compatible endpoint, called over stdlib
    HTTP so there is NO extra dependency. Get a free key at console.groq.com.

    Use for the slow loop (regime/news/reflection), not the per-bar decision.
    """

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is empty. Get a free key at console.groq.com.")
        self.api_key = api_key
        self.model = model
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def _complete(self, system: str, user: str, max_tokens: int = 600) -> str:
        payload = json.dumps({
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }).encode()
        req = urllib.request.Request(
            self.url, data=payload,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]

    def analyze(self, role: str, prompt: str, features: dict) -> dict[str, Any]:
        system = (
            f"You are the {role} analyst. Respond ONLY with JSON: "
            '{"stance": <-1..1>, "confidence": <0..1>, "summary": <str>, "evidence": [<str>]}'
        )
        return _extract_json(self._complete(system, f"{prompt}\n\nFeatures: {features}"))

    def argue(self, side: str, prompt: str) -> str:
        return self._complete(f"You are the {side} researcher. Make the strongest case.", prompt)

    def reflect(self, base: str) -> str:
        return self._complete(
            "Distill one transferable trading lesson (<=2 sentences).", base, max_tokens=120)


class ClaudeLLM:
    """Live client using the Anthropic API. Structured output via tool-use/JSON.

    Intentionally thin — wire real prompts here. Kept import-lazy so the core has
    no hard dependency on `anthropic`.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-5"):
        from anthropic import Anthropic  # local import
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def _complete(self, system: str, user: str, max_tokens: int = 600) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    def analyze(self, role: str, prompt: str, features: dict) -> dict[str, Any]:
        import json
        system = (
            f"You are the {role} analyst. Respond ONLY with JSON: "
            '{"stance": <-1..1>, "confidence": <0..1>, "summary": <str>, "evidence": [<str>]}'
        )
        raw = self._complete(system, f"{prompt}\n\nFeatures: {features}")
        try:
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        except Exception:
            data = {"stance": 0.0, "confidence": 0.3, "summary": raw[:200], "evidence": []}
        return data

    def argue(self, side: str, prompt: str) -> str:
        return self._complete(f"You are the {side} researcher. Make the strongest case.", prompt)

    def reflect(self, base: str) -> str:
        return self._complete(
            "Distill one transferable trading lesson (<=2 sentences).", base, max_tokens=120
        )


def _sign(x: float) -> float:
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def build_llm(settings) -> LLM:
    """Pick the reasoning backend. Defaults to the FREE QuantEngine (no LLM).

    `groq`/`claude` are only constructed when explicitly selected AND a key exists;
    anything else (or a missing key) falls back to the free QuantEngine so the bot
    can never silently start burning API credits.
    """
    backend = getattr(settings, "llm_backend", "quant").lower()
    try:
        if backend == "groq" and settings.groq_api_key:
            return GroqLLM(settings.groq_api_key, settings.groq_model)
        if backend == "claude" and settings.anthropic_api_key:
            return ClaudeLLM(settings.anthropic_api_key, settings.llm_model)
    except Exception:
        pass  # any backend failure -> free deterministic engine, never crash trading
    return QuantEngine()


# Backwards-compatible alias (QuantEngine was formerly MockLLM).
MockLLM = QuantEngine
