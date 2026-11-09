"""
Retrieval-grounded answering over the Constitution of India.

Pipeline per question (see CLAUDE.md for measured timings):
  1. Answer cache / verified-fact fast path.
  2. Local query handling: explicit "Article 21A" references are looked up directly
     (no Gemini round-trip for query rewriting).
  3. Hybrid search over article-level chunks: dense (MiniLM via fastembed/ONNX, no torch)
     + BM25, fused with RRF, then cross-encoder reranking.
  4. One streamed Gemini call writes the answer in labelled sections.
  5. One fast Gemini call audits the answer against the same sources.

`stream()` yields events for the SSE endpoint; `run()` consumes it and returns the
classic result dict (answer, audit, sources, model, provider, latency_ms, from_cache).
"""

import hashlib
import json
import logging
import re
import threading
import time
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

from backend.app.config import BASE_DIR, DATASET_NAME
from backend.app.models import ConstitutionalAnswer, GroundingValidation
from backend.app.services import gemini
from backend.app.services.facts import fast_path_answer, fast_path_result
from backend.app.services.ingest import DocumentChunk, build_article_chunks

logger = logging.getLogger("constitution_rag")

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
INDEX_VERSION = 2  # bump when chunking/embedding changes so stale caches are rebuilt
CACHE_DIR = BASE_DIR / "cache"
INDEX_DIR = CACHE_DIR / f"index_v{INDEX_VERSION}"
MODEL_DIR = CACHE_DIR / "models"

TOP_CANDIDATES = 20   # per retriever, before fusion
RERANK_POOL = 12      # fused candidates sent to the cross-encoder
RERANK_CHARS = 600    # chars of each candidate the cross-encoder scores
CONTEXT_CHUNKS = 5    # chunks given to the LLM
MAX_CONTEXT_CHARS = 7000
RRF_K = 60
ANSWER_CACHE_SIZE = 256

_ARTICLE_REF = re.compile(r"\b(?:article|art\.?)\s*(\d{1,3}[a-z]{0,3})\b", re.I)
_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = set(
    "a an and are as at be by can do does for from has have how i in is it its me of on or "
    "please tell that the their there this to under was what when where which who why will with "
    "about explain does mean meaning under constitution india indian".split()
)

SECTION_MARKERS = ("SUMMARY", "ANALYSIS", "EXCEPTIONS", "ARTICLES")
_SECTION_RE = re.compile(r"^\s*#{2,4}\s*(SUMMARY|ANALYSIS|EXCEPTIONS|ARTICLES)\s*:?\s*$", re.M | re.I)

SYSTEM_INSTRUCTION = (
    "You are a trusted, friendly guide who explains the Constitution of India to ordinary citizens "
    "with no legal background. Your goal is clarity and accuracy.\n"
    "Rules you MUST follow:\n"
    "1. CRITICAL: Use ONLY facts from the provided source text. Do NOT add outside knowledge, case law, "
    "or numbers that are not in the sources.\n"
    "2. CRITICAL: Only if the sources do not answer the question at all, the SUMMARY must say exactly: "
    "'The specific answer is not found in the provided constitutional text.' Then explain what the "
    "sources DO say that is related. Never use that sentence in any other section.\n"
    "3. Use short sentences and everyday words. When you use a legal term, explain it in brackets, "
    "e.g. impeachment (formal process to remove someone from office).\n"
    "4. Describe procedures as numbered steps. A short real-life comparison is welcome.\n"
    "5. Cite Articles only if they appear in the sources.\n"
    "6. Respond in EXACTLY this format, with these four headings and nothing before the first one:\n"
    "### SUMMARY\n<2-3 plain sentences>\n"
    "### ANALYSIS\n<150-250 words: what it says, how it works, who it affects, why it matters>\n"
    "### EXCEPTIONS\n<2-4 short bullet points on exceptions, conditions or limits found in the sources; "
    "if the sources state none, write '- No specific exceptions are stated in these provisions.'>\n"
    "### ARTICLES\n<comma-separated Article numbers you relied on, e.g. 21, 21A>"
)


def _tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


def parse_sections(text: str) -> Dict[str, str]:
    """Split '### SUMMARY ... ### ANALYSIS ...' text into a dict (missing sections are '')."""
    sections = {name: "" for name in SECTION_MARKERS}
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        sections["ANALYSIS"] = text.strip()
        return sections
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[m.group(1).upper()] = text[m.end():end].strip()
    return sections


def sections_to_answer(text: str) -> ConstitutionalAnswer:
    s = parse_sections(text)
    articles = [
        a.strip().removeprefix("Article").removeprefix("Art.").strip()
        for a in re.split(r"[,;\n]", s["ARTICLES"])
    ]
    articles = [a for a in articles if a and a.lower() not in {"none", "n/a", "-"}]
    return ConstitutionalAnswer(
        summary=s["SUMMARY"],
        articles_cited=articles,
        detailed_legal_analysis=s["ANALYSIS"],
        exceptions_or_limitations=s["EXCEPTIONS"],
    )


class HybridIndex:
    """Dense (fastembed MiniLM, cosine) + BM25 over article chunks, with cross-encoder reranking."""

    def __init__(self, documents: List[DocumentChunk], embeddings: np.ndarray, embedder, reranker):
        self.documents = documents
        self.embeddings = embeddings  # (n, 384), L2-normalised
        self.embedder = embedder
        self.reranker = reranker
        self.bm25 = BM25Okapi([_tokenize(d.full_text) for d in documents])
        self.by_article: Dict[str, List[int]] = {}
        for i, d in enumerate(documents):
            self.by_article.setdefault(d.article_no.upper(), []).append(i)

    def embed_query(self, text: str) -> np.ndarray:
        vec = np.asarray(next(iter(self.embedder.query_embed([text]))), dtype=np.float32)
        return vec / (np.linalg.norm(vec) + 1e-12)

    def hybrid_search(self, query: str) -> List[int]:
        scores: Dict[int, float] = {}
        tokens = _tokenize(query)
        if tokens:
            sparse = self.bm25.get_scores(tokens)
            for rank, idx in enumerate(np.argsort(sparse)[::-1][:TOP_CANDIDATES]):
                if sparse[idx] > 0:
                    scores[int(idx)] = scores.get(int(idx), 0.0) + 1.0 / (RRF_K + rank + 1)
        dense = self.embeddings @ self.embed_query(query)
        for rank, idx in enumerate(np.argsort(dense)[::-1][:TOP_CANDIDATES]):
            scores[int(idx)] = scores.get(int(idx), 0.0) + 1.0 / (RRF_K + rank + 1)
        return sorted(scores, key=scores.get, reverse=True)

    def rerank(self, query: str, candidates: List[int]) -> List[int]:
        if not candidates:
            return []
        # The cross-encoder only needs a relevance signal: scoring the heading + opening of each
        # chunk is ~5x faster and keeps ONNX memory low on small hosts (full chunks: ~1.2 s, 650 MB).
        texts = [self.documents[i].full_text[:RERANK_CHARS] for i in candidates]
        scores = list(self.reranker.rerank(query, texts, batch_size=8))
        order = np.argsort(scores)[::-1]
        return [candidates[i] for i in order]

    def retrieve(self, question: str) -> List[DocumentChunk]:
        # Explicitly named Articles are always included first.
        pinned: List[int] = []
        for ref in _ARTICLE_REF.findall(question):
            pinned.extend(self.by_article.get(ref.upper(), [])[:3])
        pinned = list(OrderedDict.fromkeys(pinned))[:CONTEXT_CHUNKS]

        candidates = [i for i in self.hybrid_search(question) if i not in pinned][:RERANK_POOL]
        ranked = self.rerank(question, candidates)
        chosen = (pinned + ranked)[:CONTEXT_CHUNKS]

        docs, total = [], 0
        for i in chosen:
            doc = self.documents[i]
            if docs and total + len(doc.content) > MAX_CONTEXT_CHARS:
                break
            docs.append(doc)
            total += len(doc.content)
        return docs


def _load_raw_lines() -> List[Optional[str]]:
    from datasets import load_dataset  # heavy import; only needed when (re)building the index

    dataset = load_dataset(DATASET_NAME, split="train")
    column = dataset.column_names[0]
    return dataset[column]


def _model_kwargs() -> Dict[str, Any]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return {"cache_dir": str(MODEL_DIR)}


def build_index_files() -> Tuple[List[DocumentChunk], np.ndarray]:
    """Download the dataset, rebuild article chunks and embeddings, and save them under INDEX_DIR."""
    from fastembed import TextEmbedding

    logger.info("Building article-level index from dataset %s ...", DATASET_NAME)
    documents = build_article_chunks(_load_raw_lines())
    embedder = TextEmbedding(EMBED_MODEL, **_model_kwargs())
    embeddings = np.asarray(list(embedder.passage_embed([d.full_text for d in documents], batch_size=32)), dtype=np.float32)
    embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX_DIR / "chunks.json", "w", encoding="utf-8") as f:
        json.dump([asdict(d) for d in documents], f, ensure_ascii=False)
    np.save(INDEX_DIR / "embeddings.npy", embeddings)
    with open(INDEX_DIR / "meta.json", "w", encoding="utf-8") as f:
        json.dump({"version": INDEX_VERSION, "dataset": DATASET_NAME, "n_docs": len(documents),
                   "embed_model": EMBED_MODEL}, f)
    logger.info("Index built: %d chunks.", len(documents))
    return documents, embeddings


def _load_index_files() -> Optional[Tuple[List[DocumentChunk], np.ndarray]]:
    meta_path = INDEX_DIR / "meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("version") != INDEX_VERSION or meta.get("dataset") != DATASET_NAME:
            return None
        rows = json.loads((INDEX_DIR / "chunks.json").read_text(encoding="utf-8"))
        documents = [DocumentChunk(**row) for row in rows]
        embeddings = np.load(INDEX_DIR / "embeddings.npy")
        if len(documents) != embeddings.shape[0]:
            return None
        return documents, embeddings
    except Exception as exc:  # noqa: BLE001 — any corruption → rebuild
        logger.warning("Index cache unreadable (%s); rebuilding.", exc)
        return None


class ConstitutionalRAG:
    def __init__(self):
        self.index: Optional[HybridIndex] = None
        self._load_lock = threading.Lock()
        self._cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    # ── loading ──────────────────────────────────────────────────────────────
    def ensure_loaded(self) -> HybridIndex:
        if self.index is not None:
            return self.index
        with self._load_lock:
            if self.index is None:
                from fastembed import TextEmbedding
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                t0 = time.perf_counter()
                loaded = _load_index_files() or build_index_files()
                documents, embeddings = loaded
                embedder = TextEmbedding(EMBED_MODEL, **_model_kwargs())
                reranker = TextCrossEncoder(RERANK_MODEL, **_model_kwargs())
                self.index = HybridIndex(documents, embeddings, embedder, reranker)
                logger.info("RAG ready: %d chunks in %.1fs", len(documents), time.perf_counter() - t0)
        return self.index

    # ── cache ────────────────────────────────────────────────────────────────
    @staticmethod
    def _cache_key(question: str) -> str:
        normalized = " ".join(question.lower().split()).rstrip("?.! ")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, key: str, result: Dict[str, Any]):
        self._cache[key] = result
        self._cache.move_to_end(key)
        while len(self._cache) > ANSWER_CACHE_SIZE:
            self._cache.popitem(last=False)

    # ── LLM steps ────────────────────────────────────────────────────────────
    @staticmethod
    def _context(docs: List[DocumentChunk]) -> str:
        return "\n\n".join(
            f"[SOURCE {i}: Article {d.article_no} | {d.part} | {d.title}]\n{d.content}"
            for i, d in enumerate(docs, 1)
        )

    @staticmethod
    def _answer_prompt(question: str, context: str) -> str:
        return (
            f"--- VERIFIED CONSTITUTIONAL SOURCE TEXT ---\n{context}\n"
            f"--- END OF SOURCES ---\n\n"
            f"Citizen's question: {question}\n\n"
            "Answer using ONLY the sources above, in the required four-section format."
        )

    @staticmethod
    def audit_grounding(answer: ConstitutionalAnswer, context: str) -> GroundingValidation:
        prompt = (
            "Audit the following answer strictly against the source context. "
            "is_faithful is true only if every factual claim is supported by the sources. "
            "List unsupported claims briefly. confidence_score is your confidence (0-1) that the "
            "answer is fully grounded.\n\n"
            f"Summary: {answer.summary}\n"
            f"Articles Cited: {answer.articles_cited}\n"
            f"Analysis: {answer.detailed_legal_analysis}\n"
            f"Exceptions: {answer.exceptions_or_limitations}\n\n"
            f"SOURCE CONTEXT:\n{context}"
        )
        audit, _ = gemini.generate_json(
            prompt, GroundingValidation,
            "You are a conservative legal auditor. If a claim is not directly grounded in the sources, flag it.",
        )
        return audit

    # ── public API ───────────────────────────────────────────────────────────
    def stream(self, question: str, use_cache: bool = True) -> Iterator[Dict[str, Any]]:
        """
        Yield events: {"type": "sources", "sources": [...]}, {"type": "delta", "text": "..."},
        and finally {"type": "final", "result": {...}} (same shape as run()).
        """
        start = time.perf_counter()
        elapsed = lambda: round((time.perf_counter() - start) * 1000, 1)  # noqa: E731
        key = self._cache_key(question)

        cached = self._cache_get(key) if use_cache else None
        if cached is not None:
            yield {"type": "final", "result": {**cached, "latency_ms": elapsed(), "from_cache": True}}
            return

        fact = fast_path_answer(question)
        if fact is not None:
            result = fast_path_result(fact, elapsed())
            self._cache_put(key, result)
            yield {"type": "final", "result": result}
            return

        index = self.ensure_loaded()
        docs = index.retrieve(question)
        sources = [
            {"article": d.article_no, "part": d.part, "title": d.title, "snippet": d.content[:220]}
            for d in docs
        ]
        yield {"type": "sources", "sources": sources}
        logger.info("Retrieved %s in %.0f ms", [d.article_no for d in docs], elapsed())

        context = self._context(docs)
        deltas, model = gemini.stream_text(self._answer_prompt(question, context), SYSTEM_INSTRUCTION)
        parts: List[str] = []
        for text in deltas:
            parts.append(text)
            yield {"type": "delta", "text": text}
        answer = sections_to_answer("".join(parts))

        try:
            audit = self.audit_grounding(answer, context)
        except Exception as exc:  # noqa: BLE001 — never lose an answer because the audit failed
            logger.warning("Grounding audit failed: %s", exc)
            audit = GroundingValidation(is_faithful=False, confidence_score=0.0,
                                        unsupported_claims=["Grounding audit unavailable for this answer."])

        result = {
            "answer": answer.model_dump(),
            "audit": audit.model_dump(),
            "sources": sources,
            "model": model,
            "provider": "Google Gemini",
            "latency_ms": elapsed(),
            "from_cache": False,
        }
        if audit.is_faithful and audit.confidence_score >= 0.85:
            self._cache_put(key, result)
        yield {"type": "final", "result": result}

    def run(self, question: str, use_cache: bool = True) -> Dict[str, Any]:
        result: Optional[Dict[str, Any]] = None
        for event in self.stream(question, use_cache=use_cache):
            if event["type"] == "final":
                result = event["result"]
        if result is None:
            raise RuntimeError("RAG pipeline produced no answer.")
        return result


if __name__ == "__main__":  # python -m backend.app.services.constitution_rag  → (re)build the index
    logging.basicConfig(level=logging.INFO)
    build_index_files()
    ConstitutionalRAG().ensure_loaded()
