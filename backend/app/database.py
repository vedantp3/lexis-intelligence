"""
Neon Postgres connection + table bootstrap.

Tables created on startup (idempotent):
  - chat_sessions  : one row per user session
  - chat_messages  : one row per message, FK → chat_sessions
"""

import logging
from contextlib import asynccontextmanager

import psycopg2
import psycopg2.extras
from psycopg2 import OperationalError

from backend.app.config import DATABASE_URL

logger = logging.getLogger("database")

# ---------------------------------------------------------------------------
# Connection helper (synchronous psycopg2 — keep it simple for MVP)
# ---------------------------------------------------------------------------

def get_connection():
    """Return a new psycopg2 connection.  Caller is responsible for closing it."""
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
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_SESSIONS_TABLE)
                cur.execute(CREATE_MESSAGES_TABLE)
                cur.execute(CREATE_SESSION_UPDATED_TRIGGER)
        conn.close()
        logger.info("Database tables initialized (Neon Postgres).")
    except OperationalError as exc:
        logger.error("Database connection failed: %s", exc)
        # Non-fatal — app still runs without DB (history features will fail gracefully)


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def upsert_session(session_id: str, user_email: str, title: str = "New Session"):
    """Insert session row if it doesn't exist yet."""
    if not DATABASE_URL:
        return
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_sessions (id, user_email, title)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (session_id, user_email, title),
                )
    finally:
        conn.close()


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
    import json

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_messages
                        (session_id, role, content, sources, audit,
                         answer_summary, articles_cited, from_cache, latency_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        role,
                        content,
                        json.dumps(sources) if sources else None,
                        json.dumps(audit) if audit else None,
                        answer_summary,
                        articles_cited,
                        from_cache,
                        latency_ms,
                    ),
                )
    finally:
        conn.close()


def get_session_messages(session_id: str, user_email: str) -> list:
    """Fetch all messages for a session, verifying ownership."""
    if not DATABASE_URL:
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Verify the session belongs to this user
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
    finally:
        conn.close()


def get_user_sessions(user_email: str) -> list:
    """Fetch all sessions for a user, most recent first."""
    if not DATABASE_URL:
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
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
    finally:
        conn.close()


def delete_session(session_id: str, user_email: str) -> bool:
    """Delete a session (and cascade-delete its messages)."""
    if not DATABASE_URL:
        return False
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM chat_sessions WHERE id = %s AND user_email = %s",
                    (session_id, user_email),
                )
                return cur.rowcount > 0
    finally:
        conn.close()
