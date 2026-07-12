"""
Pluggable LLM provider layer.

Goals:
- Works with Gemini, OpenAI, or OpenRouter through one small interface.
- Zero hard dependency: if no provider/key is configured (or a call fails),
  ``generate()`` returns ``None`` so callers fall back to the existing
  deterministic, rule-based replies. The bot therefore behaves exactly as
  before unless an operator opts in via environment variables.
- No vendor SDKs — plain REST over httpx (already a project dependency).

Configure with environment variables:
    LLM_PROVIDER   gemini | openai | openrouter | none   (default: none)
    LLM_API_KEY    provider API key
    LLM_MODEL      optional model override
    LLM_TIMEOUT_SECONDS   per-request timeout (default: 12)
    LLM_MAX_TOKENS        default max output tokens (default: 320)
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_SUPPORTED = frozenset({"gemini", "openai", "openrouter"})

_DEFAULT_MODELS = {
    # 'latest' aliases track the current supported model, so a pinned version
    # being retired for new keys won't silently break the bot. flash-lite has a
    # far more generous FREE tier than flash (which is ~20 req/day free in 2026)
    # and is plenty for empathetic replies. For production on the paid tier,
    # set LLM_MODEL=gemini-flash-latest for the higher-quality flash model.
    "gemini": "gemini-flash-lite-latest",
    "openai": "gpt-4o-mini",
    "openrouter": "google/gemini-2.5-flash",
}

# role, content pairs for optional multi-turn context
Turn = Tuple[str, str]


def provider() -> str:
    return (os.environ.get("LLM_PROVIDER") or "none").strip().lower()


def _api_key() -> str:
    return (os.environ.get("LLM_API_KEY") or "").strip()


def _model() -> str:
    override = (os.environ.get("LLM_MODEL") or "").strip()
    return override or _DEFAULT_MODELS.get(provider(), "")


def _timeout() -> float:
    try:
        return max(3.0, float(os.environ.get("LLM_TIMEOUT_SECONDS", "30")))
    except ValueError:
        return 30.0


def _max_attempts() -> int:
    """Total tries per request (1 retry by default) to ride out slow responses."""
    try:
        return max(1, int(os.environ.get("LLM_MAX_ATTEMPTS", "2")))
    except ValueError:
        return 2


def _thinking_budget() -> Optional[int]:
    """
    Gemini 'thinking' tokens are wasteful for short chat replies (they eat the
    output budget and add latency). Default 0 = disabled. Set
    LLM_THINKING_BUDGET=dynamic (or -1) to let the model decide.
    """
    raw = (os.environ.get("LLM_THINKING_BUDGET") or "0").strip().lower()
    if raw in ("", "dynamic", "auto", "-1"):
        return None
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _default_max_tokens() -> int:
    try:
        return max(32, int(os.environ.get("LLM_MAX_TOKENS", "320")))
    except ValueError:
        return 320


def is_enabled() -> bool:
    """True only when a supported provider AND an API key are configured."""
    return provider() in _SUPPORTED and bool(_api_key())


def status() -> dict:
    """Small dict for /health and admin diagnostics (no secrets leaked)."""
    return {
        "enabled": is_enabled(),
        "provider": provider(),
        "model": _model() if is_enabled() else None,
        "has_key": bool(_api_key()),
    }


def generate(
    system: str,
    user: str,
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    history: Optional[List[Turn]] = None,
) -> Optional[str]:
    """
    Return a single completion string, or ``None`` if the LLM is unavailable
    or the call fails for any reason. Callers must handle ``None`` gracefully.
    """
    if not is_enabled():
        return None

    tokens = max_tokens or _default_max_tokens()
    p = provider()
    attempts = _max_attempts()
    for attempt in range(1, attempts + 1):
        try:
            if p == "gemini":
                text = _call_gemini(system, user, temperature, tokens, history)
            else:  # openai + openrouter share the chat-completions schema
                text = _call_openai_compatible(p, system, user, temperature, tokens, history)
        except Exception as exc:
            # Transient (timeout / connection) errors are worth one more try.
            if attempt < attempts:
                logger.warning("LLM call attempt %s/%s failed (%s); retrying", attempt, attempts, exc)
                continue
            logger.warning("LLM call failed after %s attempts (provider=%s); using fallback", attempts, p)
            return None

        text = (text or "").strip()
        if text:
            return text
        # Empty (e.g. content filter / no candidate) — a retry rarely helps.
        return None
    return None


def _call_gemini(
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    history: Optional[List[Turn]],
) -> Optional[str]:
    model = _model()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    contents = []
    for role, content in history or []:
        g_role = "model" if role in ("assistant", "model") else "user"
        contents.append({"role": g_role, "parts": [{"text": content}]})
    contents.append({"role": "user", "parts": [{"text": user}]})

    generation_config = {
        "temperature": temperature,
        "maxOutputTokens": max_tokens,
    }
    budget = _thinking_budget()
    if budget is not None:
        generation_config["thinkingConfig"] = {"thinkingBudget": budget}

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": generation_config,
    }
    with httpx.Client(timeout=_timeout()) as client:
        resp = client.post(url, params={"key": _api_key()}, json=payload)
    if resp.is_error:
        if resp.status_code == 429:
            logger.info("Gemini rate limit (429); using fallback")
        else:
            logger.warning("Gemini error %s: %s", resp.status_code, resp.text[:300])
        return None
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts") or []
    return "".join(part.get("text", "") for part in parts)


def _call_openai_compatible(
    p: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    history: Optional[List[Turn]],
) -> Optional[str]:
    base = (
        "https://openrouter.ai/api/v1"
        if p == "openrouter"
        else "https://api.openai.com/v1"
    )
    messages = [{"role": "system", "content": system}]
    for role, content in history or []:
        norm = "assistant" if role in ("assistant", "model") else "user"
        messages.append({"role": norm, "content": content})
    messages.append({"role": "user", "content": user})

    payload = {
        "model": _model(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {_api_key()}"}
    with httpx.Client(timeout=_timeout()) as client:
        resp = client.post(f"{base}/chat/completions", json=payload, headers=headers)
    if resp.is_error:
        logger.warning("%s error %s: %s", p, resp.status_code, resp.text[:300])
        return None
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        return None
    return choices[0].get("message", {}).get("content", "")
