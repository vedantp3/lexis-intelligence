import json
import logging
import threading
import uuid
from typing import Any, Dict, Iterator, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.app.auth import AuthUser, require_user
from backend.app.config import GEMINI_MODEL, RAG_MODE
from backend.app.database import save_exchange
from backend.app.limiter import CHAT_RATE_LIMIT, limiter
from backend.app.models import ChatRequest, ChatResponse, HealthResponse

logger = logging.getLogger("chat_route")

router = APIRouter(prefix="/api", tags=["chat"])
_rag_instance: Optional[object] = None
_rag_lock = threading.Lock()


def get_rag():
    """Create the RAG pipeline once (RAG_MODE=full by default, lite as a low-memory fallback)."""
    global _rag_instance
    if _rag_instance is None:
        with _rag_lock:
            if _rag_instance is None:
                if RAG_MODE == "lite":
                    logger.info("RAG_MODE=lite — answering without retrieval.")
                    from backend.app.services.constitution_rag_lite import ConstitutionalRAG
                else:
                    from backend.app.services.constitution_rag import ConstitutionalRAG
                _rag_instance = ConstitutionalRAG()
    return _rag_instance


def preload_rag():
    """Load models + index ahead of the first question (called from a startup thread)."""
    try:
        get_rag().ensure_loaded()
    except Exception as exc:  # noqa: BLE001 — a failed preload just means the first request loads it
        logger.error("RAG preload failed: %s", exc)


def _validated(result: Dict[str, Any]) -> Dict[str, Any]:
    return ChatResponse(**result).model_dump()


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", service="constitution-chatbot", model=GEMINI_MODEL)


# Endpoints are plain `def` on purpose: the RAG pipeline, Gemini SDK and psycopg2 are all
# blocking, so FastAPI runs them in its threadpool instead of stalling the event loop
# (previously one slow `async def` chat request blocked every other request).

@router.post("/chat", response_model=ChatResponse)
@limiter.limit(CHAT_RATE_LIMIT)
def chat(
    request: Request,
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(require_user),
):
    """
    Answer a constitutional law question (non-streaming).

    - Requires a valid NextAuth JWT in Authorization: Bearer <token>
    - Rate limited per IP (RATE_LIMIT_PER_MINUTE)
    - Chat history is saved to Postgres after the response is sent
    """
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    session_id = body.session_id or str(uuid.uuid4())

    try:
        result = get_rag().run(question, use_cache=True)
    except Exception as exc:
        logger.error("RAG pipeline failed for user %s: %s", user.email, exc)
        background_tasks.add_task(save_exchange, session_id, user.email, question, None)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {exc}") from exc

    background_tasks.add_task(save_exchange, session_id, user.email, question, result)
    return _validated(result)


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post("/chat/stream")
@limiter.limit(CHAT_RATE_LIMIT)
def chat_stream(
    request: Request,
    body: ChatRequest,
    user: AuthUser = Depends(require_user),
):
    """
    Server-Sent Events version of /api/chat. Events, in order:
      sources → {"sources": [...]}          (retrieved Articles, before the LLM starts)
      delta   → {"text": "..."}             (answer text as it is generated, '### SECTION' format)
      final   → ChatResponse + session_id   (parsed answer + grounding audit)
      error   → {"detail": "..."}
    """
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    session_id = body.session_id or str(uuid.uuid4())
    rag = get_rag()

    def events() -> Iterator[str]:
        result: Optional[Dict[str, Any]] = None
        try:
            for event in rag.stream(question, use_cache=True):
                kind = event["type"]
                if kind == "final":
                    result = _validated(event["result"])
                    yield _sse("final", {**result, "session_id": session_id})
                elif kind == "delta":
                    yield _sse("delta", {"text": event["text"]})
                elif kind == "sources":
                    yield _sse("sources", {"sources": event["sources"]})
        except Exception as exc:  # noqa: BLE001
            logger.error("RAG stream failed for user %s: %s", user.email, exc)
            yield _sse("error", {"detail": f"Chat processing failed: {exc}"})
        finally:
            # Runs after the final event has been flushed to the client.
            save_exchange(session_id, user.email, question, result)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
