# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"Lexis Intelligence": a chatbot that answers questions about the Constitution of India in plain language. It has two parts:
- `backend/`: FastAPI on Python 3.12, deployed to Render.
- `frontend/`: Next.js 16 with NextAuth v4 (Google OAuth), meant for Vercel.

## Commands

Run the backend from the **repo root**. Imports are absolute (`from backend.app...`), so it must start as the `backend.main` module:

```bash
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
python start.py          # production entry (Procfile / render.yaml); reads $PORT
```

Frontend (run inside `frontend/`):

```bash
npm install
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

The repo has no test suite and no Python linter config.

Config comes from `backend/.env` (template: `backend/.env.example`; `config.py` loads it explicitly) and `frontend/.env.local`. `NEXTAUTH_SECRET` must be the same in both files.

## Architecture

### Request flow and auth
The browser never calls FastAPI directly. `frontend/app/page.tsx` calls Next.js server routes: `/api/proxy/chat/stream` (the main path, used by both the UI and voice mode), `/api/proxy/chat` (non-streaming) and `/api/proxy/history`. Each proxy route:
1. reads the session with `getServerSession(authOptions)` (`app/lib/authOptions.ts`);
2. **mints a new HS256 JWT** with `jose` (`app/lib/backendToken.ts`), holding `{email, name, user:{...}}` and signed with `NEXTAUTH_SECRET`;
3. forwards the request to `NEXT_PUBLIC_API_URL` with `Authorization: Bearer <token>`. The stream route pipes the backend's SSE body through unchanged.

The backend's `backend/app/auth.py` `require_user` dependency checks that token. It accepts a nested `user` claim or flat claims. If `NEXTAUTH_SECRET` is unset, it **skips signature verification** (dev mode). History rows are scoped by `user.email`.

### Backend layout
- `backend/main.py` sets up CORS (`ALLOWED_ORIGINS`, comma-separated) and the routers. On startup it loads the RAG models and index in a background thread (`PRELOAD_RAG`).
- `backend/app/api/routes/chat.py` handles `POST /api/chat`, `POST /api/chat/stream` (SSE) and `GET /api/health`. `history.py` handles `GET/DELETE /api/history`. Endpoints are **plain `def`, not `async def`, on purpose**: the RAG pipeline, Gemini SDK and psycopg2 all block, so they must run in FastAPI's threadpool.
- The rate limit is applied with the `@limiter.limit(CHAT_RATE_LIMIT)` decorator (`app/limiter.py`), placed under the route decorator. slowapi needs the parameter named `request: Request`, and each endpoint has its own counter.
- `backend/app/database.py` talks to Neon Postgres through a psycopg2 `ThreadedConnectionPool`. `_run(fn)` handles one transaction and retries once on a dead connection. psycopg2 only reuses `minconn` idle connections, so keep `minconn` ≥ 2. Chat history is written by `save_exchange()` **after** the response, in one transaction. Every DB helper does nothing if `DATABASE_URL` is unset.
- `backend/app/models.py` defines the Pydantic models. `ConstitutionalAnswer` (`summary`, `articles_cited`, `detailed_legal_analysis`, `exceptions_or_limitations`) is the answer shape stored, returned and mirrored in `frontend/app/types.ts`.
- `backend/app/services/gemini.py` is the only place that calls Gemini. Thinking is off by default (`GEMINI_THINKING_BUDGET=0`; in testing a call took ~3.1 s with thinking and ~1.0 s without). On a 503 or 429 it retries quickly, then switches to `GEMINI_FALLBACK_MODEL`. When streaming, the fallback only applies before the first token.

### RAG pipeline (`RAG_MODE`, default `full`)
`get_rag()` in `chat.py` picks the implementation. Both expose `run(question, use_cache=True)`, which returns a dict with `answer, audit, sources, model, provider, latency_ms, from_cache` (keep this shape), and `stream(question)`, which yields `sources` / `delta` / `final` events.

- **`services/constitution_rag.py` (full)** is used in production by default:
  1. answer cache (LRU, normalized question) or a verified fact from `services/facts.py`;
  2. local query handling: an "Article 21A" in the question pins that Article's chunks, with no LLM rewrite call;
  3. hybrid search over article chunks: MiniLM embeddings via **fastembed/ONNX (no torch)** with numpy cosine, plus BM25, fused with RRF and reranked by a cross-encoder;
  4. **one streamed Gemini call** writes the answer as plain text under `### SUMMARY / ### ANALYSIS / ### EXCEPTIONS / ### ARTICLES` headings (`parse_sections` / `sections_to_answer` on the backend, `parseSections` in `frontend/app/lib/chatStream.ts`; change both together);
  5. one fast JSON Gemini call audits the answer against the sources. Answers are cached only when the audit is faithful with ≥0.85 confidence.
- **`services/ingest.py`** turns the dataset into chunks. The HF dataset is raw PDF text, **one line per row**: margin headings run into the body, with page headers, running heads and footnotes mixed in. `build_article_chunks()` stitches lines into one chunk per Article (Preamble plus Articles 1–395, split above 1,800 chars), giving about 538 chunks. Never index rows one by one; that gave ~8.5k one-line fragments before.
- The index lives in `backend/cache/index_v2/` (chunks.json, embeddings.npy) and the models in `backend/cache/models/` (gitignored). Rebuild with `python -m backend.app.services.constitution_rag`; Render runs this in its build step. Bump `INDEX_VERSION` when chunking or embeddings change.
- **`services/constitution_rag_lite.py` (lite)** is a no-retrieval emergency fallback for hosts too small for the ONNX models (the backend uses ~370 MB resident locally). It returns `sources: []` and a fixed 0.55 "unverified" audit.

Measured locally on a full answer: before, about 50 s with nothing shown until the end. Now the first text appears in about 1.6 s, the checked answer is complete in about 6–7 s, and a cached question takes about 0.2 s. Retrieval adds about 0.3–1.3 s, mostly the reranker. Without the reranker, the right Article is missed for some questions (e.g. 102/103, 51A, 368).

Local-only files are gitignored and may not exist: `*_prod.py` variants, `scripts/`, `check_env.py`, `PRODUCTION_*.md`, and the notebook.

### Frontend
- `frontend/AGENTS.md` (gitignored, regenerated by `next dev`) warns that Next.js 16 has breaking changes compared with older versions. Read the docs under `frontend/node_modules/next/dist/docs/` before writing Next.js code.
- `app/lib/chatStream.ts` reads the SSE stream. `page.tsx` updates the in-progress reply by `Message.id` and shows a cursor while `streaming` is true.
- Voice mode (`app/lib/useVoiceConversation.ts` + `components/VoiceBar.tsx`) uses the browser Web Speech API (STT and TTS, Chrome/Edge). `onUtterance(text, say)` lets the page speak the summary as soon as it has streamed in. The mic stays open during playback so the user can interrupt; heard words that mostly overlap the answer being spoken are ignored as echo.
- `DESIGN.md` at the repo root holds the UI design tokens (colors, typography).
