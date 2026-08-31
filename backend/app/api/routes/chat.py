import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.auth import AuthUser, require_user
from backend.app.database import save_message, upsert_session
from backend.app.models import ChatRequest, ChatResponse, HealthResponse

logger = logging.getLogger("chat_route")

router = APIRouter(prefix="/api", tags=["chat"])
_rag_instance: Optional[object] = None


def get_rag():
    """Initialize the heavy RAG stack on first use, not during app import/startup."""
    global _rag_instance
    if _rag_instance is None:
        logger.info("Initializing ConstitutionalRAG on first chat request...")
        from backend.app.services.constitution_rag import ConstitutionalRAG

        _rag_instance = ConstitutionalRAG()
    return _rag_instance


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", service="constitution-chatbot", model="gemini-2.5-flash")


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    user: AuthUser = Depends(require_user),
):
    """
    Process a constitutional law question.

    - Requires a valid NextAuth JWT in Authorization: Bearer <token>
    - Rate limited by slowapi (configured in main.py)
    - Persists question + answer to Neon Postgres (if DATABASE_URL is set)
    - Uses in-memory cache for repeated questions (cache key = SHA-256 of question)
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Resolve or generate session ID
    session_id = request.session_id or str(uuid.uuid4())

    # Ensure session exists in DB (idempotent)
    upsert_session(
        session_id=session_id,
        user_email=user.email,
        title=request.question[:80],  # First 80 chars of the question become the session title
    )

    # Save the user message
    save_message(session_id=session_id, role="user", content=request.question)

    try:
        result = get_rag().run(request.question, use_cache=True)
    except Exception as exc:
        logger.error("RAG pipeline failed for user %s: %s", user.email, exc)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(exc)}") from exc

    # Save the assistant message with full metadata
    answer_obj = result["answer"]
    save_message(
        session_id=session_id,
        role="assistant",
        content=answer_obj.get("detailed_legal_analysis", ""),
        sources=result.get("sources"),
        audit=result.get("audit"),
        answer_summary=answer_obj.get("summary"),
        articles_cited=answer_obj.get("articles_cited"),
        from_cache=result.get("from_cache", False),
        latency_ms=result.get("latency_ms"),
    )

    return ChatResponse(
        answer=result["answer"],
        audit=result["audit"],
        sources=result["sources"],
        model=result["model"],
        provider=result["provider"],
        latency_ms=result["latency_ms"],
        from_cache=result.get("from_cache", False),
    )
