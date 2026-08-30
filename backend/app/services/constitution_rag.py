import hashlib
import json
import logging
import os
import pickle
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Suppress Windows symlink warning from HuggingFace
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import faiss
import numpy as np
from datasets import load_dataset
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

from google import genai
from google.genai import types

from backend.app.config import BASE_DIR, DATASET_NAME, GEMINI_API_KEY
from backend.app.models import ConstitutionalAnswer, GroundingValidation, QueryAnalysis

logger = logging.getLogger("constitution_rag")

TARGET_MODEL = "gemini-2.5-flash"
EMBED_MODEL = "all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOP_CANDIDATES = 20
RERANK_TOP_N = 4
RRF_K = 60
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# Retry config for Gemini
GEMINI_MAX_RETRIES = 4
GEMINI_RETRY_BASE_DELAY = 3.0  # seconds, doubles each retry

# Signals that indicate a transient/retryable Gemini error
_RETRYABLE_SIGNALS = (
    "503", "429", "unavailable", "rate limit", "quota",
    "resource exhausted", "too many requests", "server error",
    "overloaded", "high demand", "try again",
)


def _is_retryable_gemini_error(exc: Exception) -> bool:
    """Return True if this Gemini exception is transient and worth retrying."""
    msg = str(exc).lower()
    return any(signal in msg for signal in _RETRYABLE_SIGNALS)


# ── Constitutional Facts Fast-Path ────────────────────────────────────────────
# Verified facts about the Constitution of India that are NOT in the article
# text itself. These are answered directly without RAG retrieval.
CONSTITUTIONAL_FACTS: List[Dict[str, Any]] = [
    {
        "keywords": ["how many articles", "total articles", "number of articles", "how many article"],
        "answer": (
            "The Constitution of India originally had **395 Articles** when it came into effect "
            "on 26 January 1950. Over the years, many amendments have been made, and today it has "
            "around **448 Articles** (some original articles were deleted, and new ones were added). "
            "It is divided into **25 Parts** and has **12 Schedules** (lists of important details). "
            "This makes it one of the longest written constitutions in the world!"
        ),
    },
    {
        "keywords": ["how many schedules", "total schedules", "number of schedules"],
        "answer": (
            "The Constitution originally had **8 Schedules** in 1950. After amendments, it now has "
            "**12 Schedules**. Each Schedule is like an annexure — it lists specific details, "
            "such as the list of states, official languages, and anti-defection rules."
        ),
    },
    {
        "keywords": ["how many parts", "total parts", "number of parts"],
        "answer": (
            "The Constitution is currently divided into **25 Parts** (originally 22 Parts in 1950). "
            "Each Part groups related articles together — for example, Part III covers Fundamental Rights, "
            "Part IV covers Directive Principles, and Part XI covers relations between the Centre and States."
        ),
    },
    {
        "keywords": ["how many amendments", "total amendments", "number of amendments"],
        "answer": (
            "As of 2024, the Constitution has been amended **106 times** through Constitutional "
            "Amendment Acts. The first amendment was in 1951. The 42nd Amendment (1976) was the most "
            "sweeping, often called the 'Mini-Constitution'. The 44th Amendment (1978) reversed several "
            "controversial changes from the Emergency era."
        ),
    },
    {
        "keywords": ["how many fundamental rights", "number of fundamental rights", "total fundamental rights"],
        "answer": (
            "There are currently **6 Fundamental Rights** in Part III of the Constitution "
            "(Articles 12–35). Originally there were 7, but the Right to Property (Article 31) "
            "was removed in 1978 by the 44th Amendment and made a legal right instead. "
            "The 6 rights are: (1) Right to Equality, (2) Right to Freedom, "
            "(3) Right against Exploitation, (4) Right to Freedom of Religion, "
            "(5) Cultural and Educational Rights, (6) Right to Constitutional Remedies."
        ),
    },
    {
        "keywords": ["how many directive principles", "number of dpsp", "total directive principles"],
        "answer": (
            "The Directive Principles of State Policy (DPSP) are listed in Part IV "
            "(Articles 36–51) of the Constitution. There are approximately **16 articles** "
            "covering the Directive Principles. They are guidelines for the government — "
            "unlike Fundamental Rights, they cannot be enforced in court, but the government "
            "is expected to follow them when making laws."
        ),
    },
    {
        "keywords": ["when was constitution adopted", "when constitution came into effect", 
                     "constitution day", "when was constitution enacted", "when constitution enacted"],
        "answer": (
            "The Constitution of India was **adopted on 26 November 1949** by the Constituent Assembly. "
            "It came into **effect (enforced) on 26 January 1950**, which is why we celebrate "
            "Republic Day on January 26 every year. The Constituent Assembly took about **2 years, "
            "11 months, and 18 days** to draft it."
        ),
    },
]


def _fast_path_answer(question: str) -> Optional[str]:
    """Check if question matches a known constitutional fact. Returns answer text or None."""
    q = question.lower().strip()
    for fact in CONSTITUTIONAL_FACTS:
        if any(kw in q for kw in fact["keywords"]):
            return fact["answer"]
    return None

@dataclass
class DocumentChunk:
    doc_id: int
    part: str
    article_no: str
    title: str
    content: str

    @property
    def full_text(self) -> str:
        return (
            f"Part: {self.part} | Article: {self.article_no} | Title: {self.title}\n"
            f"Provisions: {self.content}"
        )


class HybridIndex:
    def __init__(self, documents: List[DocumentChunk]):
        self.documents = documents
        # Use local_files_only if models are already cached — skips all HuggingFace HTTP HEAD requests
        local_only = self._models_cached()
        if local_only:
            logger.info("Loading models from local cache (offline mode)...")
        self.bi_encoder = SentenceTransformer(EMBED_MODEL, local_files_only=local_only)
        self.reranker = CrossEncoder(RERANK_MODEL, local_files_only=local_only)
        self.vector_index: Optional[faiss.Index] = None
        self.bm25: Optional[BM25Okapi] = None
        self._build_or_load()

    @staticmethod
    def _models_cached() -> bool:
        """Return True if both models exist in the HuggingFace cache directory."""
        import huggingface_hub
        cache_dir = Path(huggingface_hub.constants.HF_HUB_CACHE)
        embed_cached = any((cache_dir / d).exists() for d in [
            "models--sentence-transformers--all-MiniLM-L6-v2",
        ])
        rerank_cached = any((cache_dir / d).exists() for d in [
            "models--cross-encoder--ms-marco-MiniLM-L6-v2",
            "models--cross-encoder--ms-marco-MiniLM-L-6-v2",
        ])
        return embed_cached and rerank_cached

    def _paths(self) -> Tuple[Path, Path, Path]:
        return (
            CACHE_DIR / "faiss_index.index",
            CACHE_DIR / "bm25.pkl",
            CACHE_DIR / "meta.json",
        )

    def _build_or_load(self):
        faiss_path, bm25_path, meta_path = self._paths()

        if all(p.exists() for p in (faiss_path, bm25_path, meta_path)):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("n_docs") == len(self.documents):
                    logger.info("Loading cached retrieval indexes...")
                    self.vector_index = faiss.read_index(str(faiss_path))
                    with open(bm25_path, "rb") as f:
                        self.bm25 = pickle.load(f)
                    return
            except Exception as exc:
                logger.warning("Cache load failed: %s. Rebuilding index.", exc)

        logger.info("Building retrieval indexes for %d documents...", len(self.documents))
        texts = [doc.full_text for doc in self.documents]
        embeddings = self.bi_encoder.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=True,
            batch_size=32,
        )
        faiss.normalize_L2(embeddings)
        self.vector_index = faiss.IndexFlatIP(embeddings.shape[1])
        self.vector_index.add(embeddings)
        self.bm25 = BM25Okapi([text.lower().split() for text in texts])

        faiss.write_index(self.vector_index, str(faiss_path))
        with open(bm25_path, "wb") as f:
            pickle.dump(self.bm25, f)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"n_docs": len(self.documents), "dataset": DATASET_NAME}, f)

    def hybrid_search(self, queries: List[str], target_article: Optional[str] = None) -> List[DocumentChunk]:
        rrf_scores: Dict[int, float] = {}

        for query in queries:
            sparse_scores = self.bm25.get_scores(query.lower().split())
            sparse_top = np.argsort(sparse_scores)[::-1][:TOP_CANDIDATES]
            for rank, idx in enumerate(sparse_top):
                rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)

            q_emb = self.bi_encoder.encode([query], convert_to_numpy=True)
            faiss.normalize_L2(q_emb)
            _, dense_top = self.vector_index.search(q_emb, TOP_CANDIDATES)
            for rank, idx in enumerate(dense_top[0]):
                rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)

        if target_article:
            target = target_article.lower().replace("article", "").strip()
            for idx, doc in enumerate(self.documents):
                if target == doc.article_no.lower():
                    rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 2.0

        ranked_indices = sorted(rrf_scores.keys(), key=lambda i: rrf_scores[i], reverse=True)[:TOP_CANDIDATES]
        return [self.documents[i] for i in ranked_indices]

    def rerank(self, query: str, candidates: List[DocumentChunk]) -> List[DocumentChunk]:
        if not candidates:
            return []
        pairs = [[query, candidate.full_text] for candidate in candidates]
        scores = self.reranker.predict(pairs)
        order = np.argsort(scores)[::-1][:RERANK_TOP_N]
        return [candidates[i] for i in order]


class ConstitutionalRAG:
    def __init__(self):
        self.documents: List[DocumentChunk] = []
        self.index: Optional[HybridIndex] = None
        self.client = None
        self._cache: Dict[str, Any] = {}
        self._initialize_client()

    def _initialize_client(self):
        if GEMINI_API_KEY:
            self.client = genai.Client(api_key=GEMINI_API_KEY)

    def _cache_key(self, question: str) -> str:
        return hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()

    def ensure_loaded(self):
        chunks_path = CACHE_DIR / "chunks.pkl"
        meta_path   = CACHE_DIR / "meta.json"

        if not self.documents:
            # Try loading pre-processed chunks from disk first
            if chunks_path.exists() and meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    if meta.get("dataset") == DATASET_NAME:
                        logger.info("Loading cached chunks from disk (%s)...", chunks_path)
                        with open(chunks_path, "rb") as f:
                            self.documents = pickle.load(f)
                        logger.info("Loaded %d chunks from cache.", len(self.documents))
                except Exception as exc:
                    logger.warning("Chunk cache load failed: %s. Re-ingesting.", exc)
                    self.documents = []

            if not self.documents:
                self.documents = self._ingest_constitution()
                # Save chunks to disk for fast future restarts
                with open(chunks_path, "wb") as f:
                    pickle.dump(self.documents, f)
                logger.info("Saved %d chunks to cache.", len(self.documents))

        if self.index is None:
            self.index = HybridIndex(self.documents)

    def _ingest_constitution(self) -> List[DocumentChunk]:
        logger.info("Loading dataset: %s", DATASET_NAME)
        dataset = load_dataset(DATASET_NAME, split="train")
        documents: List[DocumentChunk] = []
        seen = set()

        sample = dataset[0] if len(dataset) > 0 else {}
        columns = list(sample.keys()) if sample else []

        # ── Column detection: support both old and new dataset schemas ─────────
        id_col = None
        content_col = None

        ID_CANDIDATES = [
            "article_id", "id", "article_no", "Article_Number",
            "article_number", "number", "Article_No",
        ]
        CONTENT_CANDIDATES = [
            "article_desc", "text", "content", "article_content",
            "description", "body", "provisions", "Article_Description",
        ]

        for col in columns:
            if col in ID_CANDIDATES and id_col is None:
                id_col = col
            if col in CONTENT_CANDIDATES and content_col is None:
                content_col = col

        # Fallback: pick the column with the longest average content
        if not content_col:
            content_col = max(
                columns,
                key=lambda c: sum(len(str(dataset[i].get(c, ""))) for i in range(min(10, len(dataset)))),
            )

        logger.info(
            "Dataset '%s' — detected columns: id_col=%s, content_col=%s | total columns: %s",
            DATASET_NAME, id_col, content_col, columns,
        )

        for row in dataset:
            article_id = str(row.get(id_col, "")).strip() if id_col else ""
            desc = str(row.get(content_col, "")).strip()

            if not desc or len(desc) < 30:
                continue

            digest = hashlib.md5(desc.lower().encode("utf-8")).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)

            art_match = re.search(r"(?:Article\s*)?(\d+[A-Za-z]?)", article_id or desc, flags=re.I)
            article_no = art_match.group(1) if art_match else "General"

            part_match = re.search(r"(Part\s+[IVXLCDM]+)", desc, flags=re.I)
            part = part_match.group(1) if part_match else "Constitution"

            title = article_id if article_id else f"Article {article_no}"
            documents.append(
                DocumentChunk(
                    doc_id=len(documents),
                    part=part,
                    article_no=article_no,
                    title=title,
                    content=desc,
                )
            )

        logger.info("Loaded %d constitutional chunks from '%s'", len(documents), DATASET_NAME)
        if len(documents) == 0:
            raise RuntimeError(
                f"Dataset '{DATASET_NAME}' produced 0 valid chunks. "
                f"Columns found: {columns}. Check the dataset structure."
            )
        return documents

    def _call_gemini(self, prompt: str, schema: Any, system_instruction: Optional[str] = None):
        """
        Call Gemini with structured JSON output.
        Retries on rate-limit (429) and service errors (503) with exponential backoff.
        """
        if self.client is None:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        last_exc = None
        for attempt in range(GEMINI_MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model=TARGET_MODEL,
                    contents=prompt,
                    config=config,
                )
                return schema.model_validate_json(response.text)
            except Exception as exc:
                if _is_retryable_gemini_error(exc):
                    last_exc = exc
                    delay = GEMINI_RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Gemini transient error (attempt %d/%d): %s — retrying in %.1fs",
                        attempt + 1, GEMINI_MAX_RETRIES, exc, delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error("Gemini non-retryable error: %s", exc)
                    raise

        logger.error("Gemini API failed after %d retries: %s", GEMINI_MAX_RETRIES, last_exc)
        raise RuntimeError(f"Gemini API unavailable after {GEMINI_MAX_RETRIES} retries. Please try again shortly.")


    def analyze_query(self, question: str) -> QueryAnalysis:
        prompt = (
            "Analyze this question about the Indian Constitution. "
            "Return classification, 2-3 legal search rewrites, and a target Article if explicitly requested.\n\n"
            f"Question: {question}"
        )
        return self._call_gemini(prompt, QueryAnalysis)

    def _compress_context(self, docs: List[DocumentChunk]) -> str:
        parts = []
        for doc in docs:
            clean_lines = [line.strip() for line in doc.content.splitlines() if len(line.strip()) > 20]
            body = "\n".join(clean_lines)
            parts.append(f"[SOURCE: Article {doc.article_no} | {doc.part}]\n{body}")
        return "\n\n" + ("=" * 60) + "\n\n".join(parts)

    def generate_answer(self, question: str, context: str) -> ConstitutionalAnswer:
        prompt = (
            f"--- VERIFIED CONSTITUTIONAL SOURCE TEXT ---\n{context}\n"
            f"------------------------------------------\n\n"
            f"Citizen's question: {question}\n\n"
            f"Using ONLY the source text above, answer the question in plain, simple English that any "
            f"ordinary person can understand. Structure your answer step-by-step. "
            f"Explain every legal term in brackets. Use real-world comparisons. "
            f"Do not assume the reader has any legal background."
        )
        system_instruction = (
            "You are a trusted, friendly guide who explains the Indian Constitution to ordinary citizens — "
            "farmers, students, shopkeepers, homemakers — people with no legal background. "
            "Your goal is clarity, not impressiveness. "
            "Rules you MUST follow:\n"
            "1. Write like you're explaining to a 16-year-old, not a lawyer.\n"
            "2. Use short sentences. Use everyday words.\n"
            "3. If you use a legal term (like 'impeachment', 'resolution', 'quorum'), "
            "   immediately explain it in simple brackets: impeachment (formal accusation/removal process).\n"
            "4. Use real-life analogies — compare constitutional processes to everyday situations.\n"
            "5. Structure explanations as numbered steps when describing procedures.\n"
            "6. CRITICAL: Only use facts from the provided source text. Do NOT add outside knowledge.\n"
            "7. CRITICAL: If the source text does NOT directly answer the question, then in the "
            "   'summary' field write exactly: 'The specific answer is not found in the provided "
            "   constitutional text.' In 'detailed_legal_analysis', explain what the source DOES say "
            "   that is related, and be honest that you cannot give the exact answer from this source.\n"
            "8. NEVER invent numbers, counts, or facts that are not in the source text.\n"
            "9. The 'summary' must be 2-3 plain sentences. No legal language.\n"
            "10. The 'detailed_legal_analysis' must be at least 300 words."
        )
        return self._call_gemini(prompt, ConstitutionalAnswer, system_instruction)


    def audit_grounding(self, answer: ConstitutionalAnswer, context: str) -> GroundingValidation:
        prompt = (
            "Audit the following legal answer strictly against the source context. "
            "Flag unsupported assertions.\n\n"
            f"Summary: {answer.summary}\n"
            f"Articles Cited: {answer.articles_cited}\n"
            f"Analysis: {answer.detailed_legal_analysis}\n"
            f"Exceptions: {answer.exceptions_or_limitations}\n\n"
            f"SOURCE CONTEXT:\n{context}"
        )
        system_instruction = "You are a conservative legal auditor. If the answer is not directly grounded, flag it."
        return self._call_gemini(prompt, GroundingValidation, system_instruction)

    def run(self, question: str, use_cache: bool = True) -> Dict[str, Any]:
        start = time.perf_counter()
        key = self._cache_key(question)

        if use_cache and key in self._cache:
            result = dict(self._cache[key])
            result["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
            result["from_cache"] = True
            return result

        # ── Fast-path: known constitutional facts ─────────────────────────────
        fast_answer = _fast_path_answer(question)
        if fast_answer is not None:
            logger.info("Fast-path answer triggered for: %s", question[:80])
            result = {
                "answer": {
                    "summary": fast_answer.split(".")[0] + ".",
                    "articles_cited": [],
                    "detailed_legal_analysis": fast_answer,
                    "exceptions_or_limitations": (
                        "This is a general fact about the Constitution as a whole. "
                        "For details about specific articles, ask about that article directly."
                    ),
                },
                "audit": {
                    "is_faithful": True,
                    "confidence_score": 1.0,
                    "unsupported_claims": [],
                },
                "sources": [],
                "model": "constitutional-facts-db",
                "provider": "Verified Facts",
                "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                "from_cache": False,
            }
            self._cache[key] = result
            return result

        # ── Full RAG pipeline ─────────────────────────────────────────────────
        self.ensure_loaded()
        plan = self.analyze_query(question)
        candidates = self.index.hybrid_search(plan.rewritten_queries, plan.target_article_filter)
        top_docs = self.index.rerank(question, candidates)
        context = self._compress_context(top_docs)

        answer = self.generate_answer(question, context)
        audit = self.audit_grounding(answer, context)

        result = {
            "answer": answer.model_dump(),
            "audit": audit.model_dump(),
            "sources": [
                {
                    "article": doc.article_no,
                    "part": doc.part,
                    "title": doc.title,
                    "snippet": doc.content[:220],
                }
                for doc in top_docs
            ],
            "model": TARGET_MODEL,
            "provider": "Google Gemini",
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "from_cache": False,
        }

        if audit.is_faithful and audit.confidence_score >= 0.85:
            self._cache[key] = result

        return result
