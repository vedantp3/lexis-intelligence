import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from backend.app.config import GEMINI_API_KEY
from backend.app.models import ConstitutionalAnswer

logger = logging.getLogger("constitution_rag_lite")

TARGET_MODEL = "gemini-2.5-flash"
GEMINI_MAX_RETRIES = 4
GEMINI_RETRY_BASE_DELAY = 3.0

_RETRYABLE_SIGNALS = (
    "503", "429", "unavailable", "rate limit", "quota",
    "resource exhausted", "too many requests", "server error",
    "overloaded", "high demand", "try again",
)

CONSTITUTIONAL_FACTS: List[Dict[str, Any]] = [
    {
        "keywords": ["how many articles", "total articles", "number of articles", "how many article"],
        "answer": (
            "The Constitution of India originally had **395 Articles** when it came into effect "
            "on 26 January 1950. Over the years, many amendments have been made, and today it has "
            "around **448 Articles**. It is divided into **25 Parts** and has **12 Schedules**."
        ),
    },
    {
        "keywords": ["how many schedules", "total schedules", "number of schedules"],
        "answer": (
            "The Constitution originally had **8 Schedules** in 1950. After amendments, it now has "
            "**12 Schedules**."
        ),
    },
    {
        "keywords": ["how many parts", "total parts", "number of parts"],
        "answer": (
            "The Constitution is currently divided into **25 Parts**. It originally had 22 Parts "
            "when it came into force on 26 January 1950."
        ),
    },
    {
        "keywords": ["how many fundamental rights", "number of fundamental rights", "total fundamental rights"],
        "answer": (
            "There are currently **6 Fundamental Rights** in Part III of the Constitution "
            "(Articles 12 to 35). Originally there were 7, but the Right to Property was later "
            "removed from the list of Fundamental Rights."
        ),
    },
]


def _is_retryable_gemini_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(signal in msg for signal in _RETRYABLE_SIGNALS)


def _fast_path_answer(question: str) -> Optional[str]:
    q = question.lower().strip()
    for fact in CONSTITUTIONAL_FACTS:
        if any(kw in q for kw in fact["keywords"]):
            return fact["answer"]
    return None


class ConstitutionalRAG:
    """
    Lightweight production-safe fallback for Render.
    Avoids importing local embedding/reranker stacks that restart the service
    on low-memory instances, while still returning structured answers.
    """

    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _cache_key(self, question: str) -> str:
        return hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()

    def _call_gemini(self, prompt: str, schema: Any, system_instruction: Optional[str] = None):
        if self.client is None:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        last_exc = None
        for attempt in range(GEMINI_MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model=TARGET_MODEL,
                    contents=prompt,
                    config=config,
                )
                return schema.model_validate_json(response.text)
            except Exception as exc:
                if _is_retryable_gemini_error(exc):
                    last_exc = exc
                    delay = GEMINI_RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Gemini transient error (attempt %d/%d): %s — retrying in %.1fs",
                        attempt + 1, GEMINI_MAX_RETRIES, exc, delay,
                    )
                    time.sleep(delay)
                    continue
                raise

        raise RuntimeError(
            f"Gemini API unavailable after {GEMINI_MAX_RETRIES} retries: {last_exc}"
        )

    def _generate_direct_answer(self, question: str) -> ConstitutionalAnswer:
        prompt = (
            "Answer this question about the Constitution of India in plain English. "
            "Be accurate and cautious. Include relevant article numbers only when you are confident. "
            "If the exact answer is uncertain, say so clearly instead of guessing.\n\n"
            f"Question: {question}"
        )
        system_instruction = (
            "You are a helpful constitutional law assistant for Indian users.\n"
            "Rules:\n"
            "1. Keep the summary to 2-3 simple sentences.\n"
            "2. The detailed_legal_analysis should be at least 220 words.\n"
            "3. Explain legal terms in simple brackets.\n"
            "4. Use article numbers only when confident.\n"
            "5. Do not invent citations or pretend you checked source passages.\n"
            "6. In exceptions_or_limitations, mention any uncertainty or practical limits."
        )
        return self._call_gemini(prompt, ConstitutionalAnswer, system_instruction)

    def run(self, question: str, use_cache: bool = True) -> Dict[str, Any]:
        start = time.perf_counter()
        key = self._cache_key(question)

        if use_cache and key in self._cache:
            result = dict(self._cache[key])
            result["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
            result["from_cache"] = True
            return result

        fast_answer = _fast_path_answer(question)
        if fast_answer is not None:
            result = {
                "answer": {
                    "summary": fast_answer.split(".")[0] + ".",
                    "articles_cited": [],
                    "detailed_legal_analysis": fast_answer,
                    "exceptions_or_limitations": (
                        "This is a general constitutional fact. "
                        "For article-wise detail, ask about a specific topic or article."
                    ),
                },
                "audit": {
                    "is_faithful": True,
                    "confidence_score": 1.0,
                    "unsupported_claims": [],
                },
                "sources": [],
                "model": "constitutional-facts-db",
                "provider": "Verified Facts",
                "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                "from_cache": False,
            }
            self._cache[key] = result
            return result

        answer = self._generate_direct_answer(question)
        result = {
            "answer": answer.model_dump(),
            "audit": {
                "is_faithful": False,
                "confidence_score": 0.55,
                "unsupported_claims": [
                    "Production-safe mode is active, so this response was generated without local retrieval sources."
                ],
            },
            "sources": [],
            "model": TARGET_MODEL,
            "provider": "Google Gemini (Lite Mode)",
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "from_cache": False,
        }
        self._cache[key] = result
        return result
