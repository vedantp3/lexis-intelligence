# Lexis Intelligence — Constitution of India AI Chatbot

A full-stack RAG (Retrieval-Augmented Generation) chatbot that answers questions about the **Constitution of India** in plain, citizen-friendly language.

![Tech Stack](https://img.shields.io/badge/Next.js-16-black?logo=next.js) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi) ![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-blue?logo=google) ![Neon](https://img.shields.io/badge/Neon-Postgres-teal)

---

## Features

- 🔍 **Hybrid RAG** — FAISS vector search + BM25 keyword search + cross-encoder reranking
- 🤖 **Gemini 2.5 Flash** — structured JSON answers with grounding audit
- 🔐 **Google OAuth** — sign in with Google via NextAuth.js
- 💾 **Chat history** — saved to Neon Postgres per user session
- ⚡ **Fast facts** — instant answers for common questions (article count, schedules, etc.)
- 🛡️ **Rate limiting** — per-IP via slowapi
- 📱 **Responsive UI** — premium dark/light design

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, TypeScript, NextAuth.js |
| Backend | FastAPI, Python 3.12 |
| Vector DB | FAISS (in-process) + BM25 |
| Database | Neon Postgres (psycopg2) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM | Google Gemini 2.5 Flash |
| Dataset | [moonmelonpizza/constitution_of_india](https://huggingface.co/datasets/moonmelonpizza/constitution_of_india) |
| Auth | Google OAuth 2.0 via NextAuth |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- A [Google Gemini API key](https://aistudio.google.com/)
- A [Neon Postgres](https://neon.tech) database (free tier works)
- Google OAuth credentials from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)

### 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/constitution-ai.git
cd constitution-ai
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
copy backend\.env.example backend\.env
# Edit backend/.env with your real values
```

### 3. Frontend Setup

```bash
cd frontend
npm install

# Configure environment
copy .env.local.example .env.local
# Edit frontend/.env.local with your real values
```

### 4. Run

**Terminal 1 — Backend:**
```bash
# From project root
.venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) → Sign in with Google → Start chatting.

> **First startup:** The backend downloads and indexes the dataset (~2 min). Subsequent restarts load from cache in ~5 seconds.

---

## Project Structure

```
constitution-ai/
├── backend/
│   ├── main.py                        # FastAPI entry point
│   ├── requirements.txt
│   ├── .env.example                   # Environment template
│   └── app/
│       ├── config.py                  # Settings from .env
│       ├── models.py                  # Pydantic request/response models
│       ├── database.py                # Neon Postgres (chat history)
│       ├── auth.py                    # JWT verification (NextAuth tokens)
│       ├── api/routes/
│       │   ├── chat.py                # POST /api/chat
│       │   └── history.py             # GET/DELETE /api/history
│       └── services/
│           └── constitution_rag.py    # Full RAG pipeline
├── frontend/
│   ├── app/
│   │   ├── page.tsx                   # Main chat UI
│   │   ├── login/page.tsx             # Login page
│   │   ├── components/                # AuthGuard, AuditBadge, SourceCard
│   │   ├── api/
│   │   │   ├── auth/[...nextauth]/    # NextAuth handler
│   │   │   └── proxy/                 # Server-side proxies (chat, history)
│   │   └── lib/authOptions.ts         # Shared NextAuth config
│   ├── .env.local.example
│   └── package.json
└── README.md
```

---

## How the RAG Pipeline Works

```
User Question
     │
     ▼
Fast-path check (known facts like "how many articles?") ──→ Instant answer
     │ (if not a known fact)
     ▼
Gemini: analyze_query() → rewrites question 2-3 ways + classifies
     │
     ▼
Hybrid Search: FAISS (semantic) + BM25 (keyword) → top 20 candidates
     │
     ▼
CrossEncoder reranker → top 4 most relevant chunks
     │
     ▼
Gemini: generate_answer() → plain-English structured answer
     │
     ▼
Gemini: audit_grounding() → faithfulness check + confidence score
     │
     ▼
Save to Neon Postgres → Return to user
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key |
| `DATASET_NAME` | HuggingFace dataset name |
| `DATABASE_URL` | Neon Postgres connection string |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `NEXTAUTH_SECRET` | Same secret as frontend NextAuth |
| `ENABLE_RATE_LIMITING` | `true` / `false` |
| `RATE_LIMIT_PER_MINUTE` | Requests per IP per minute (default: 5) |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `NEXTAUTH_SECRET` | Random secret (generate with `openssl rand -base64 32`) |
| `NEXTAUTH_URL` | Your frontend URL (e.g. `http://localhost:3000`) |
| `NEXT_PUBLIC_API_URL` | Backend URL (e.g. `http://localhost:8000`) |

---

## License

MIT
