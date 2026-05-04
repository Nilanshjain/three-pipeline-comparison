"""
Provider-agnostic LLM completion client.

Pipelines 1 and 2 call ``complete()`` instead of talking to a vendor SDK
directly. Provider is chosen via ``LLM_PROVIDER`` in .env. Default is Groq
(zero-cost via Llama 3.3 70B free tier); Gemini is kept as a one-env-var
fallback in case Groq rate-limits us mid-eval.

All providers return the same shape:

    @dataclass
    class CompletionResult:
        text: str
        prompt_tokens: int
        completion_tokens: int
        model: str

so callers don't branch on provider type.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.core.config import settings


# Pricing per 1M tokens (input, output) in USD.
# Groq's free tier is $0 — kept here so cost_usd in PipelineResult stays
# meaningful if we ever switch to paid. Gemini Flash kept as the fallback.
PRICING_USD_PER_1M: dict[str, dict[str, tuple[float, float]]] = {
    "groq": {
        "llama-3.3-70b-versatile": (0.0, 0.0),     # free tier
        "llama-3.1-8b-instant": (0.0, 0.0),        # free tier
        "meta-llama/llama-4-scout-17b-16e-instruct": (0.0, 0.0),  # free tier
        "openai/gpt-oss-20b": (0.0, 0.0),
        "qwen/qwen3-32b": (0.0, 0.0),
    },
    "gemini": {
        "gemini-2.5-flash": (0.0, 0.0),            # free tier within RPD limits
        "gemini-2.5-flash-lite": (0.0, 0.0),
        "gemini-2.5-pro": (1.25, 10.0),            # paid only
    },
}


@dataclass
class CompletionResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str


def cost_usd(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p_in, p_out = PRICING_USD_PER_1M.get(provider, {}).get(model, (0.0, 0.0))
    return prompt_tokens * p_in / 1_000_000 + completion_tokens * p_out / 1_000_000


async def complete(prompt: str, *, provider: str | None = None, model: str | None = None) -> CompletionResult:
    """Run a single completion against the configured provider."""
    provider = (provider or settings.llm_provider).lower()
    model = model or settings.llm_model

    if provider == "groq":
        return await _complete_groq(prompt, model)
    if provider == "gemini":
        return await _complete_gemini(prompt, model)
    raise ValueError(f"Unknown LLM_PROVIDER={provider!r}. Expected 'groq' or 'gemini'.")


# ---------- Groq ----------

_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY missing in .env (needed when LLM_PROVIDER=groq)")
        # max_retries: SDK auto-retries 429 (and 5xx) with exponential backoff.
        # Bumped from default 2 -> 5 because during ECC ingestion, Groq quota
        # is heavily contended — short retry budgets give spurious failures.
        # Per-call timeout is generous to cover backoff sleeps.
        _groq_client = Groq(api_key=settings.groq_api_key, max_retries=5, timeout=120.0)
    return _groq_client


async def _complete_groq(prompt: str, model: str) -> CompletionResult:
    client = _get_groq_client()

    def _call() -> Any:
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )

    # Outer retry handles the case where Groq's built-in retries exhaust.
    # We treat the third hit on RateLimitError as a real failure to surface
    # to the caller, but most ingestion-time 429s resolve within 1-2 cycles.
    last_err = None
    for attempt in range(3):
        try:
            resp = await asyncio.to_thread(_call)
            usage = resp.usage
            return CompletionResult(
                text=resp.choices[0].message.content or "",
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                model=model,
            )
        except Exception as e:
            last_err = e
            # Heuristic match: groq SDK raises groq.RateLimitError but to
            # avoid a hard import of internals, check the message.
            msg = str(e)
            if "429" in msg or "rate_limit" in msg.lower() or "Too Many Requests" in msg:
                # Already retried internally by SDK; add a final outer backoff
                # to let the ECC's rate-limit storm drain before giving up.
                await asyncio.sleep(8 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"Groq call failed after retries: {last_err}")


# ---------- Gemini (fallback) ----------

_gemini_models: dict[str, Any] = {}


def _get_gemini_model(name: str):
    if name in _gemini_models:
        return _gemini_models[name]
    import google.generativeai as genai
    key = settings.gemini_api_key or settings.google_api_key
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing in .env (needed when LLM_PROVIDER=gemini)")
    genai.configure(api_key=key)
    m = genai.GenerativeModel(name)
    _gemini_models[name] = m
    return m


async def _complete_gemini(prompt: str, model: str) -> CompletionResult:
    m = _get_gemini_model(model)
    resp = await asyncio.to_thread(m.generate_content, prompt)
    usage = getattr(resp, "usage_metadata", None)
    return CompletionResult(
        text=resp.text,
        prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
        completion_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        model=model,
    )
