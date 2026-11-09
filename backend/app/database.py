"""
Neon Postgres connection + table bootstrap.

Tables created on startup (idempotent):
  - chat_sessions  : one row per user session
  - chat_messages  : one row per message, FK → chat_sessions
"""

import json
import logging
import threading
from typing import Any, Callable, Dict, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2 import InterfaceError, OperationalError

from backend.app.config import DATABASE_URL

logger = logging.getLogger("database")

# ---------------------------------------------------------------------------
# Connection pool
#
# Opening a fresh TLS connection to Neon costs ~100-300 ms and a chat request
# used to open three in a row. Connections are now pooled and reused. Neon
# drops idle connections (scale-to-zero), so an operation that hits a dead
# pooled connection discards it and retries once on a fresh one.
# ---------------------------------------------------------------------------

_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                # psycopg2 keeps at most `minconn` idle connections and closes the rest on
                # putconn, so minconn is the number actually reused between requests.
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    2, 6, DATABASE_URL,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                    keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
                )
    return _pool


def _run(fn: Callable[[Any], Any]) -> Any:
    """Run fn(cursor) inside one transaction on a pooled connection, retrying once if the connection was dead."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured in .env")
    pool = _get_pool()
    for attempt in range(2):
        conn = pool.getconn()
        broken = False
        try:
            with conn:  # commit on success, rollback on error
                with conn.cursor() as cur:
                    return fn(cur)
        except (OperationalError, InterfaceError):
            broken = True
            if attempt == 1:
                raise
            logger.warning("Pooled DB connection was dead; retrying on a fresh one.")
        finally:
            pool.putconn(conn, close=broken or conn.closed != 0)


def get_connection():
    """Return a new standalone psycopg2 connection.  Caller is responsible for closing it."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured in .env")
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    id          TEXT        PRIMARY KEY,
    user_email  TEXT        NOT NULL,
    title       TEXT        NOT NULL DEFAULT 'New Session',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id              SERIAL      PRIMARY KEY,
    session_id      TEXT        NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT        NOT NULL,
    sources         JSONB,
    audit           JSONB,
    answer_summary  TEXT,
    articles_cited  TEXT[],
    from_cache      BOOLEAN     DEFAULT FALSE,
    latency_ms      FLOAT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_SESSION_UPDATED_TRIGGER = """
CREATE OR REPLACE FUNCTION update_session_timestamp()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    UPDATE chat_sessions SET updated_at = NOW() WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_session_updated'
    ) THEN
        CREATE TRIGGER trg_session_updated
        AFTER INSERT ON chat_messages
        FOR EACH ROW EXECUTE FUNCTION update_session_timestamp();
    END IF;
END;
$$;
"""


def init_db():
    """Create all tables if they do not exist.  Called once at server startup."""
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set — skipping database initialization.")
        return
    try:
        def create(cur):
            cur.execute(CREATE_SESSIONS_TABLE)
            cur.execute(CREATE_MESSAGES_TABLE)
            cur.execute(CREATE_SESSION_UPDATED_TRIGGER)

        _run(create)
        logger.info("Database tables initialized (Neon Postgres).")
    except (OperationalError, InterfaceError) as exc:
        logger.error("Database connection failed: %s", exc)
        # Non-fatal — app still runs without DB (history features will fail gracefully)


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

_INSERT_SESSION = """
    INSERT INTO chat_sessions (id, user_email, title)
    VALUES (%s, %s, %s)
    ON CONFLICT (id) DO NOTHING
"""

_INSERT_MESSAGE = """
    INSERT INTO chat_messages
        (session_id, role, content, sources, audit,
         answer_summary, articles_cited, from_cache, latency_ms)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _message_params(session_id, role, content, sources=None, audit=None, answer_summary=None,
                    articles_cited=None, from_cache=False, latency_ms=None):
    return (
        session_id,
        role,
        content,
        json.dumps(sources) if sources else None,
        json.dumps(audit) if audit else None,
        answer_summary,
        articles_cited,
        from_cache,
        latency_ms,
    )


def upsert_session(session_id: str, user_email: str, title: str = "New Session"):
    """Insert session row if it doesn't exist yet."""
    if not DATABASE_URL:
        return
    _run(lambda cur: cur.execute(_INSERT_SESSION, (session_id, user_email, title)))


def save_message(
    session_id: str,
    role: str,
    content: str,
    sources=None,
    audit=None,
    answer_summary: str = None,
    articles_cited=None,
    from_cache: bool = False,
    latency_ms: float = None,
):
    """Append a message to the session."""
    if not DATABASE_URL:
        return
    params = _message_params(session_id, role, content, sources, audit, answer_summary,
                             articles_cited, from_cache, latency_ms)
    _run(lambda cur: cur.execute(_INSERT_MESSAGE, params))


def save_exchange(session_id: str, user_email: str, question: str, result: Optional[Dict[str, Any]]):
    """
    Persist one question/answer exchange in a single transaction on one connection
    (session upsert + user message + assistant message). Runs after the response has
    been sent, so it never adds to user-visible latency. `result` is the RAG result
    dict, or None if answering failed (only the question is stored then).
    """
    if not DATABASE_URL:
        return

    def write(cur):
        cur.execute(_INSERT_SESSION, (session_id, user_email, question[:80]))
        cur.execute(_INSERT_MESSAGE, _message_params(session_id, "user", question))
        if result:
            answer = result.get("answer") or {}
            cur.execute(_INSERT_MESSAGE, _message_params(
                session_id,
                "assistant",
                answer.get("detailed_legal_analysis", ""),
                sources=result.get("sources"),
                audit=result.get("audit"),
                answer_summary=answer.get("summary"),
                articles_cited=answer.get("articles_cited"),
                from_cache=result.get("from_cache", False),
                latency_ms=result.get("latency_ms"),
            ))

    try:
        _run(write)
    except Exception as exc:  # noqa: BLE001 — history is non-critical; never fail the chat
        logger.error("Failed to save chat history for session %s: %s", session_id, exc)


def get_session_messages(session_id: str, user_email: str) -> list:
    """Fetch all messages for a session, verifying ownership."""
    if not DATABASE_URL:
        return []

    def read(cur):
        cur.execute(
            "SELECT id FROM chat_sessions WHERE id = %s AND user_email = %s",
            (session_id, user_email),
        )
        if cur.fetchone() is None:
            return []
        cur.execute(
            "SELECT * FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC",
            (session_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    return _run(read)


def get_user_sessions(user_email: str) -> list:
    """Fetch all sessions for a user, most recent first."""
    if not DATABASE_URL:
        return []

    def read(cur):
        cur.execute(
            """
            SELECT s.id, s.title, s.created_at, s.updated_at,
                   (SELECT content FROM chat_messages
                    WHERE session_id = s.id AND role = 'user'
                    ORDER BY created_at ASC LIMIT 1) AS first_question
            FROM chat_sessions s
            WHERE s.user_email = %s
            ORDER BY s.updated_at DESC
            LIMIT 50
            """,
            (user_email,),
        )
        return [dict(row) for row in cur.fetchall()]

    return _run(read)


def delete_session(session_id: str, user_email: str) -> bool:
    """Delete a session (and cascade-delete its messages)."""
    if not DATABASE_URL:
        return False

    def delete(cur):
        cur.execute(
            "DELETE FROM chat_sessions WHERE id = %s AND user_email = %s",
            (session_id, user_email),
        )
        return cur.rowcount > 0

    return _run(delete)
