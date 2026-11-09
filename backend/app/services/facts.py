"""Verified constitutional facts answered instantly, without retrieval (shared by both RAG modes)."""
from typing import Any, Dict, List, Optional

CONSTITUTIONAL_FACTS: List[Dict[str, Any]] = [
    {
        "keywords": ["how many articles", "total articles", "number of articles", "how many article"],
        "answer": (
            "The Constitution of India originally had **395 Articles** when it came into effect "
            "on 26 January 1950. Over the years, many amendments have been made, and today it has "
            "around **448 Articles** (some original articles were deleted, and new ones were added). "
            "It is divided into **25 Parts** and has **12 Schedules** (lists of important details). "
            "This makes it one of the longest written constitutions in the world!"
        ),
    },
    {
        "keywords": ["how many schedules", "total schedules", "number of schedules"],
        "answer": (
            "The Constitution originally had **8 Schedules** in 1950. After amendments, it now has "
            "**12 Schedules**. Each Schedule is like an annexure — it lists specific details, "
            "such as the list of states, official languages, and anti-defection rules."
        ),
    },
    {
        "keywords": ["how many parts", "total parts", "number of parts"],
        "answer": (
            "The Constitution is currently divided into **25 Parts** (originally 22 Parts in 1950). "
            "Each Part groups related articles together — for example, Part III covers Fundamental Rights, "
            "Part IV covers Directive Principles, and Part XI covers relations between the Centre and States."
        ),
    },
    {
        "keywords": ["how many amendments", "total amendments", "number of amendments"],
        "answer": (
            "As of 2024, the Constitution has been amended **106 times** through Constitutional "
            "Amendment Acts. The first amendment was in 1951. The 42nd Amendment (1976) was the most "
            "sweeping, often called the 'Mini-Constitution'. The 44th Amendment (1978) reversed several "
            "controversial changes from the Emergency era."
        ),
    },
    {
        "keywords": ["how many fundamental rights", "number of fundamental rights", "total fundamental rights"],
        "answer": (
            "There are currently **6 Fundamental Rights** in Part III of the Constitution "
            "(Articles 12–35). Originally there were 7, but the Right to Property (Article 31) "
            "was removed in 1978 by the 44th Amendment and made a legal right instead. "
            "The 6 rights are: (1) Right to Equality, (2) Right to Freedom, "
            "(3) Right against Exploitation, (4) Right to Freedom of Religion, "
            "(5) Cultural and Educational Rights, (6) Right to Constitutional Remedies."
        ),
    },
    {
        "keywords": ["how many directive principles", "number of dpsp", "total directive principles"],
        "answer": (
            "The Directive Principles of State Policy (DPSP) are listed in Part IV "
            "(Articles 36–51) of the Constitution. There are approximately **16 articles** "
            "covering the Directive Principles. They are guidelines for the government — "
            "unlike Fundamental Rights, they cannot be enforced in court, but the government "
            "is expected to follow them when making laws."
        ),
    },
    {
        "keywords": ["when was constitution adopted", "when constitution came into effect", 
                     "constitution day", "when was constitution enacted", "when constitution enacted"],
        "answer": (
            "The Constitution of India was **adopted on 26 November 1949** by the Constituent Assembly. "
            "It came into **effect (enforced) on 26 January 1950**, which is why we celebrate "
            "Republic Day on January 26 every year. The Constituent Assembly took about **2 years, "
            "11 months, and 18 days** to draft it."
        ),
    },
]


def fast_path_answer(question: str) -> Optional[str]:
    """Return a verified fact answer if the question matches a known fact, else None."""
    q = question.lower().strip()
    for fact in CONSTITUTIONAL_FACTS:
        if any(kw in q for kw in fact["keywords"]):
            return fact["answer"]
    return None


def fast_path_result(answer_text: str, latency_ms: float) -> Dict[str, Any]:
    return {
        "answer": {
            "summary": answer_text.split(".")[0] + ".",
            "articles_cited": [],
            "detailed_legal_analysis": answer_text,
            "exceptions_or_limitations": (
                "This is a general fact about the Constitution as a whole. "
                "For details about specific articles, ask about that article directly."
            ),
        },
        "audit": {"is_faithful": True, "confidence_score": 1.0, "unsupported_claims": []},
        "sources": [],
        "model": "constitutional-facts-db",
        "provider": "Verified Facts",
        "latency_ms": latency_ms,
        "from_cache": False,
    }
