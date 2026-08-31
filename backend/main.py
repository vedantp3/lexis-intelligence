import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.history import router as history_router
from backend.app.config import (
    ALLOWED_ORIGINS,
    BACKEND_HOST,
    BACKEND_PORT,
    ENABLE_RATE_LIMITING,
    LOG_LEVEL,
    RATE_LIMIT_PER_MINUTE,
)
from backend.app.database import init_db

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, enabled=ENABLE_RATE_LIMITING)


# ── App lifespan (startup / shutdown) ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Constitution AI backend...")
    init_db()  # Create Neon Postgres tables if they don't exist
    
    # Preloading thread removed to prevent Out-Of-Memory (Exit Code 137) crashes 
    # on low-resource free hosting tiers. The RAG pipeline will load on demand.
    
    yield
    logger.info("Shutting down Constitution AI backend.")



# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Lexis Intelligence — Constitution of India API",
    version="2.0.0",
    description="AI-powered constitutional law research API with hybrid RAG retrieval.",
    lifespan=lifespan,
)

# Rate limit error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(history_router)


# Apply rate limit to the chat endpoint specifically
# (5 requests/minute per IP by default, configurable via RATE_LIMIT_PER_MINUTE)
from backend.app.api.routes.chat import chat as chat_endpoint
limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")(chat_endpoint)


@app.get("/")
async def root():
    return {
        "service": "Lexis Intelligence — Constitution of India API",
        "version": "2.0.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host=BACKEND_HOST, port=BACKEND_PORT, reload=True)
