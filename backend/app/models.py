from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Inbound ──────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    history: List[ChatMessage] = Field(default_factory=list)
    session_id: Optional[str] = Field(default=None, description="Client-generated UUID for this chat session")


# ── RAG internals ─────────────────────────────────────────────────────────────

class QueryAnalysis(BaseModel):
    category: str = Field(description="Factual_Article | Conceptual | Procedural | Comparative")
    rewritten_queries: List[str] = Field(..., min_length=1)
    target_article_filter: Optional[str] = Field(default=None)


class ConstitutionalAnswer(BaseModel):
    summary: str = Field(
        description=(
            "A 2-3 sentence plain-English summary a 10th grader could understand. "
            "State WHAT the law does and WHY it matters in simple, everyday language. "
            "No legal jargon. No Latin. No citations in this field."
        )
    )
    articles_cited: List[str] = Field(
        description="List of Article numbers cited, e.g. ['Article 61', 'Article 65']"
    )
    detailed_legal_analysis: str = Field(
        description=(
            "A thorough, step-by-step explanation written in plain, conversational English "
            "that any ordinary citizen can follow. Structure it as numbered steps or clear paragraphs. "
            "When you must use a legal term, immediately explain it in simple words in parentheses. "
            "Use real-world analogies or comparisons to make abstract concepts concrete. "
            "Cover: (1) what the provision says in simple terms, (2) how it works in practice "
            "step-by-step, (3) who is affected and how, (4) a real-world example or analogy, "
            "(5) why this provision matters to ordinary citizens. "
            "Minimum 300 words. Do NOT use legal jargon without explaining it."
        )
    )
    exceptions_or_limitations: str = Field(
        description=(
            "In 2-4 plain-English bullet points, list any exceptions, special conditions, "
            "or situations where this provision does NOT apply. "
            "Explain each exception as if talking to a friend, not a lawyer."
        )
    )



class GroundingValidation(BaseModel):
    is_faithful: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    unsupported_claims: List[str] = Field(default_factory=list)


class SourceChunk(BaseModel):
    article: str
    part: str
    title: str
    snippet: str


# ── Outbound ──────────────────────────────────────────────────────────────────

class ChatResponse(BaseModel):
    answer: ConstitutionalAnswer
    audit: GroundingValidation
    sources: List[SourceChunk]
    model: str
    provider: str
    latency_ms: float
    from_cache: bool = False


class HealthResponse(BaseModel):
    status: str
    service: str
    model: str


# ── History models (returned by /api/history endpoints) ──────────────────────

class HistoryMessage(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    sources: Optional[List[SourceChunk]] = None
    audit: Optional[GroundingValidation] = None
    answer_summary: Optional[str] = None
    articles_cited: Optional[List[str]] = None
    from_cache: bool = False
    latency_ms: Optional[float] = None
    created_at: datetime


class SessionSummary(BaseModel):
    id: str
    title: str
    first_question: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SessionDetail(BaseModel):
    session: SessionSummary
    messages: List[HistoryMessage]
