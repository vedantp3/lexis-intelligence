"""
Emergency fallback (RAG_MODE=lite): no retrieval, Gemini answers directly.

Kept for hosts that cannot fit even the ONNX models in memory. Answers are NOT grounded
in source text, which the fixed audit below makes explicit to the user.
"""

import hashlib
import time
from typing import Any, Dict

from backend.app.models import ConstitutionalAnswer
from backend.app.services import gemini
from backend.app.services.facts import fast_path_answer, fast_path_result

SYSTEM_INSTRUCTION = (
    "You are a helpful constitutional law assistant for Indian users.\n"
    "Rules:\n"
    "1. Keep the summary to 2-3 simple sentences.\n"
    "2. The detailed_legal_analysis should be 150-250 words.\n"
    "3. Explain legal terms in simple brackets.\n"
    "4. Use article numbers only when confident.\n"
    "5. Do not invent citations or pretend you checked source passages.\n"
    "6. In exceptions_or_limitations, mention any uncertainty or practical limits."
)


class ConstitutionalRAG:
    """Lightweight production-safe fallback without local retrieval."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def ensure_loaded(self):
        return None

    @staticmethod
    def _cache_key(question: str) -> str:
        return hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()

    def run(self, question: str, use_cache: bool = True) -> Dict[str, Any]:
        start = time.perf_counter()
        elapsed = lambda: round((time.perf_counter() - start) * 1000, 1)  # noqa: E731
        key = self._cache_key(question)

        if use_cache and key in self._cache:
            return {**self._cache[key], "latency_ms": elapsed(), "from_cache": True}

        fact = fast_path_answer(question)
        if fact is not None:
            result = fast_path_result(fact, elapsed())
            self._cache[key] = result
            return result

        prompt = (
            "Answer this question about the Constitution of India in plain English. "
            "Be accurate and cautious. Include relevant article numbers only when you are confident. "
            "If the exact answer is uncertain, say so clearly instead of guessing.\n\n"
            f"Question: {question}"
        )
        answer, model = gemini.generate_json(prompt, ConstitutionalAnswer, SYSTEM_INSTRUCTION)
        result = {
            "answer": answer.model_dump(),
            "audit": {
                "is_faithful": False,
                "confidence_score": 0.55,
                "unsupported_claims": [
                    "Lite mode is active, so this response was generated without retrieving source text."
                ],
            },
            "sources": [],
            "model": model,
            "provider": "Google Gemini (Lite Mode)",
            "latency_ms": elapsed(),
            "from_cache": False,
        }
        self._cache[key] = result
        return result

    def stream(self, question: str, use_cache: bool = True):
        yield {"type": "final", "result": self.run(question, use_cache)}
