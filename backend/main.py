import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.app.api.routes.chat import preload_rag
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.history import router as history_router
from backend.app.config import ALLOWED_ORIGINS, BACKEND_HOST, BACKEND_PORT, LOG_LEVEL, PRELOAD_RAG
from backend.app.database import init_db
from backend.app.limiter import limiter

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


# ── App lifespan (startup / shutdown) ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Constitution AI backend...")
    init_db()  # Create Neon Postgres tables if they don't exist

    # Load the ONNX models + index in the background so the first question doesn't pay
    # for it. (The old torch stack was too heavy to preload on 512 MB hosts; the fastembed
    # stack is ~400 MB peak. Set PRELOAD_RAG=false or RAG_MODE=lite if memory is tight.)
    if PRELOAD_RAG:
        threading.Thread(target=preload_rag, name="rag-preload", daemon=True).start()

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
