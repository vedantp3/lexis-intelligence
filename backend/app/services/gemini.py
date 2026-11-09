"""
Shared Gemini client helpers.

Latency choices (measured, see CLAUDE.md):
  - Thinking is OFF by default (GEMINI_THINKING_BUDGET=0). On gemini-2.5-flash this cut a
    small structured call from ~3.1 s to ~1.0 s; answers are grounded in supplied context,
    so extra reasoning tokens bought little.
  - Transient errors (503 "high demand", 429) retry quickly once, then fall back to a
    lighter model instead of sleeping 3 → 6 → 12 → 24 s.
"""

import logging
import time
from typing import Any, Iterator, List, Optional

from google import genai
from google.genai import types

from backend.app.config import (
    GEMINI_API_KEY,
    GEMINI_FALLBACK_MODEL,
    GEMINI_MODEL,
    GEMINI_THINKING_BUDGET,
)

logger = logging.getLogger("gemini")

_RETRYABLE_SIGNALS = (
    "503", "429", "500", "unavailable", "rate limit", "quota",
    "resource exhausted", "too many requests", "server error",
    "overloaded", "high demand", "try again", "deadline",
)
ATTEMPTS_PER_MODEL = 2
RETRY_DELAY_S = 1.0

_client: Optional[genai.Client] = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(signal in msg for signal in _RETRYABLE_SIGNALS)


def _models() -> List[str]:
    models = [GEMINI_MODEL]
    if GEMINI_FALLBACK_MODEL and GEMINI_FALLBACK_MODEL != GEMINI_MODEL:
        models.append(GEMINI_FALLBACK_MODEL)
    return models


def _config(
    schema: Any = None,
    system_instruction: Optional[str] = None,
    temperature: float = 0.0,
    max_output_tokens: Optional[int] = None,
) -> types.GenerateContentConfig:
    config = types.GenerateContentConfig(temperature=temperature)
    if schema is not None:
        config.response_mime_type = "application/json"
        config.response_schema = schema
    if system_instruction:
        config.system_instruction = system_instruction
    if max_output_tokens:
        config.max_output_tokens = max_output_tokens
    if GEMINI_THINKING_BUDGET >= 0:
        config.thinking_config = types.ThinkingConfig(thinking_budget=GEMINI_THINKING_BUDGET)
    return config


def _with_fallback(call):
    """Run call(model) with quick retries, then the fallback model. Returns (result, model)."""
    last_exc: Optional[Exception] = None
    for model in _models():
        for attempt in range(ATTEMPTS_PER_MODEL):
            try:
                return call(model), model
            except Exception as exc:  # noqa: BLE001 — SDK raises several error types
                if not is_retryable(exc):
                    raise
                last_exc = exc
                logger.warning("Gemini %s transient error (attempt %d): %s", model, attempt + 1, str(exc)[:160])
                if attempt + 1 < ATTEMPTS_PER_MODEL:
                    time.sleep(RETRY_DELAY_S)
    raise RuntimeError(f"Gemini is busy right now. Please try again shortly. ({last_exc})")


def generate_json(prompt: str, schema: Any, system_instruction: Optional[str] = None):
    """Structured JSON call validated into the given Pydantic schema. Returns (parsed, model)."""
    config = _config(schema=schema, system_instruction=system_instruction)

    def call(model: str):
        response = get_client().models.generate_content(model=model, contents=prompt, config=config)
        return schema.model_validate_json(response.text)

    return _with_fallback(call)


def stream_text(prompt: str, system_instruction: Optional[str] = None, max_output_tokens: int = 2048):
    """
    Stream plain text. Returns (iterator_of_text_deltas, model).

    Retries/fallback apply until the first chunk arrives; after that, errors propagate
    (we can't un-send text that the user has already seen).
    """
    config = _config(system_instruction=system_instruction, temperature=0.2, max_output_tokens=max_output_tokens)

    def call(model: str):
        stream = get_client().models.generate_content_stream(model=model, contents=prompt, config=config)
        iterator = iter(stream)
        first = next(iterator, None)  # forces the request; transient errors surface here
        return first, iterator

    (first, iterator), model = _with_fallback(call)

    def deltas() -> Iterator[str]:
        if first is not None and first.text:
            yield first.text
        for chunk in iterator:
            if chunk.text:
                yield chunk.text

    return deltas(), model
