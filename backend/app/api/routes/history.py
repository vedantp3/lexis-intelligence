"""
Chat history endpoints.

GET  /api/history                        → list all sessions for authenticated user
GET  /api/history/{session_id}           → get all messages for a session
DELETE /api/history/{session_id}         → delete a session
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.auth import AuthUser, require_user
from backend.app.database import delete_session, get_session_messages, get_user_sessions
from backend.app.models import HistoryMessage, SessionDetail, SessionSummary

logger = logging.getLogger("history_route")

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=List[SessionSummary])
async def list_sessions(user: AuthUser = Depends(require_user)):
    """Return all sessions for the authenticated user, most recent first."""
    rows = get_user_sessions(user.email)
    return [
        SessionSummary(
            id=row["id"],
            title=row["title"],
            first_question=row.get("first_question"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, user: AuthUser = Depends(require_user)):
    """Return all messages in a session.  Returns 404 if session not found or not owned by user."""
    rows = get_session_messages(session_id, user.email)
    if rows is None or (isinstance(rows, list) and len(rows) == 0):
        # Could be genuinely empty OR not owned — treat both as 404 for security
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    first = rows[0] if rows else {}
    session_meta = SessionSummary(
        id=session_id,
        title=first.get("session_title", "Session"),
        first_question=next(
            (r["content"] for r in rows if r["role"] == "user"), None
        ),
        created_at=first.get("created_at", first.get("session_created_at")),
        updated_at=rows[-1].get("created_at", first.get("created_at")),
    )

    messages = []
    for row in rows:
        import json
        sources_raw = row.get("sources")
        audit_raw = row.get("audit")
        messages.append(
            HistoryMessage(
                id=row["id"],
                session_id=session_id,
                role=row["role"],
                content=row["content"],
                sources=json.loads(sources_raw) if isinstance(sources_raw, str) else sources_raw,
                audit=json.loads(audit_raw) if isinstance(audit_raw, str) else audit_raw,
                answer_summary=row.get("answer_summary"),
                articles_cited=row.get("articles_cited"),
                from_cache=row.get("from_cache", False),
                latency_ms=row.get("latency_ms"),
                created_at=row["created_at"],
            )
        )

    return SessionDetail(session=session_meta, messages=messages)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_session(session_id: str, user: AuthUser = Depends(require_user)):
    """Delete a session and all its messages."""
    deleted = delete_session(session_id, user.email)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
