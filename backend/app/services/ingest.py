"""
Rebuild article-level chunks from the raw dataset.

The HF dataset (`moonmelonpizza/constitution_of_india`) is the PDF text of the Constitution,
one *line* per row, in reading order: marginal headings glued to body text with runs of
spaces, page headers, running heads, footnote markers and footnote text. Treating each row
as a document (the old ingestion) produced ~8.5k one-line fragments averaging 57 chars, with
article numbers guessed from footnote dates. This module stitches the lines back into one
chunk per Article (split further only when an Article is very long).
"""

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

MAX_CHUNK_CHARS = 1800

_GAP = re.compile(r"\s{6,}")
_ARTICLE_START = re.compile(r"^(?:\d{0,2}\[|\*\[|\*|\[)?\s*(\d{1,3})([A-Z]{0,3})\.\s+(?=\S)")
# Repealed ranges such as "379.—391. Rep. by ..."
_ARTICLE_RANGE = re.compile(r"^(\d{1,3})\.?\s*[—–�-]\s*(\d{1,3})\.\s*")
_PART_LINE = re.compile(r"^\d{0,2}\[?\s*PART\s+([IVXL]+[A-Z]?)\]?\s*$")
_RUNNING_HEAD = re.compile(r"^\(Part\s+([IVXL]+[A-Z]?)\.")
_LONE_MARKER = re.compile(r"^[\d*]{1,3}$")
_FOOTNOTE_START = re.compile(
    r"^(Subs\.|Ins\.|Omitted|Rep\.|Added|Renumbered|Am\.|The words|Cl\.|Sub-cl|Now |See |Certain|"
    r"Proviso|Arts?\.|Para|Explanation|The brackets|Earlier|In its|Sub-section|Item|Entry|Shall)"
)
_INLINE_MARKER = re.compile(r"(?<![\w(])\d{1,2}\s?(?=\[)|(?<=\s)\d{1,2}(?=\*{3})")


@dataclass
class DocumentChunk:
    doc_id: int
    part: str
    article_no: str
    title: str
    content: str

    @property
    def full_text(self) -> str:
        return f"Article {self.article_no} ({self.part}) — {self.title}\n{self.content}"


def _clean(text: str) -> str:
    text = text.replace("�", "—").replace("\x0c", " ")
    text = _INLINE_MARKER.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_long(text: str, limit: int = MAX_CHUNK_CHARS) -> List[str]:
    if len(text) <= limit:
        return [text]
    pieces: List[str] = []
    current = ""
    # Prefer splitting before clause markers "(2)", then sentence ends.
    for unit in re.split(r"(?=\(\d+[A-Z]?\)\s)|(?<=[.;:])\s+", text):
        if not unit:
            continue
        if len(current) + len(unit) + 1 > limit and current:
            pieces.append(current.strip())
            current = unit
        else:
            current = f"{current} {unit}" if current else unit
    if current.strip():
        pieces.append(current.strip())
    return pieces


class _Article:
    def __init__(self, number: str, part: str):
        self.number = number
        self.part = part
        self.title_parts: List[str] = []
        self.title_open = True
        self.title_side = "left"
        self.body: List[str] = []

    @property
    def title(self) -> str:
        title = _clean(" ".join(self.title_parts)).rstrip(".")
        return title[:120] if title else f"Article {self.number}"


def build_article_chunks(lines: Iterable[Optional[str]], part_titles: Optional[dict] = None) -> List[DocumentChunk]:
    part_titles = dict(part_titles or {})
    current_part = "Preamble"
    pending_part_title: Optional[str] = None
    in_footnotes = False
    in_running_head = False
    prev_marker = False
    last_num = 0

    preamble: List[str] = []
    articles: List[_Article] = []
    article: Optional[_Article] = None

    for raw in lines:
        if raw is None:
            continue
        if "\x0c" in raw:
            in_footnotes = False  # new page
        line = raw.replace("\x0c", "").rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        # Page header: "THE CONSTITUTION OF INDIA      11"
        if stripped.startswith("THE CONSTITUTION OF INDIA") and _GAP.search(line):
            continue
        if in_footnotes:
            continue
        if in_running_head:
            in_running_head = not stripped.endswith(")")
            continue
        head = _RUNNING_HEAD.match(stripped)
        if head:
            current_part = f"Part {head.group(1)}"
            in_running_head = not stripped.endswith(")")
            continue
        if _LONE_MARKER.match(stripped):
            prev_marker = True
            continue
        if prev_marker and _FOOTNOTE_START.match(stripped):
            in_footnotes = True
            prev_marker = False
            continue
        prev_marker = False

        part_match = _PART_LINE.match(stripped)
        if part_match:
            current_part = f"Part {part_match.group(1)}"
            pending_part_title = current_part
            continue
        if pending_part_title:
            if stripped.isupper() or stripped.upper() == stripped:
                part_titles.setdefault(pending_part_title, stripped.title())
                pending_part_title = None
                continue
            pending_part_title = None

        pieces = [p.strip() for p in _GAP.split(line.strip()) if p.strip()]

        # Article start: number at the beginning of the line, or after a left-margin heading.
        start_idx = None
        for idx in range(min(2, len(pieces))):
            m = _ARTICLE_START.match(pieces[idx])
            if m:
                n = int(m.group(1))
                if last_num <= n <= last_num + 6:
                    start_idx = idx
                    break
        rng = _ARTICLE_RANGE.match(pieces[0]) if pieces else None
        if rng and last_num <= int(rng.group(1)) <= last_num + 6:
            last_num = int(rng.group(2))
            article = _Article(f"{rng.group(1)}-{rng.group(2)}", current_part)
            article.title_open = False
            article.title_parts.append("Repealed")
            articles.append(article)
            article.body.append(" ".join(pieces))
            continue
        if start_idx is not None:
            m = _ARTICLE_START.match(pieces[start_idx])
            last_num = int(m.group(1))
            article = _Article(m.group(1) + m.group(2), current_part)
            articles.append(article)
            if start_idx == 1:  # "Heading text      21. Body..."
                article.title_parts.append(pieces[0])
                body_pieces = pieces[1:]
            elif len(pieces) > 1 and len(pieces[-1]) < 40:  # "21A. Body...      Heading."
                article.title_side = "right"
                article.title_parts.append(pieces[-1])
                body_pieces = pieces[:-1]
            else:
                body_pieces = pieces
            if article.title_parts and article.title_parts[-1].endswith("."):
                article.title_open = False
            article.body.append(" ".join(body_pieces))
            continue

        if article is None:
            preamble.append(" ".join(pieces))
            continue

        # Continuation of a marginal heading?
        if article.title_open:
            if len(pieces) > 1:
                heading_piece = pieces[0] if article.title_side == "left" else pieces[-1]
                if len(heading_piece) < 40:
                    article.title_parts.append(heading_piece)
                    rest = pieces[1:] if article.title_side == "left" else pieces[:-1]
                    article.body.append(" ".join(rest))
                    article.title_open = not heading_piece.endswith(".") and len(article.title_parts) < 5
                    continue
            elif len(stripped) < 30 and not _ARTICLE_START.match(stripped) and not stripped.startswith("("):
                article.title_parts.append(stripped)
                article.title_open = not stripped.endswith(".") and len(article.title_parts) < 5
                continue
            article.title_open = False
        article.body.append(" ".join(pieces))

    chunks: List[DocumentChunk] = []

    def add(part: str, number: str, title: str, text: str):
        part_label = f"{part} — {part_titles[part]}" if part in part_titles else part
        for piece in _split_long(text):
            chunks.append(DocumentChunk(len(chunks), part_label, number, title, piece))

    if preamble:
        add("Preamble", "Preamble", "Preamble", _clean(" ".join(preamble)))
    for art in articles:
        body = _clean(" ".join(art.body))
        if len(body) >= 15:
            add(art.part, art.number, art.title, body)
    return chunks
