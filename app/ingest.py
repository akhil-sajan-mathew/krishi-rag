"""Parse source PDFs, clean and chunk them, embed the chunks, and load them into Postgres.

Usage:
  python -m app.ingest --config size512_overlap64            # full run
  python -m app.ingest --config size512_overlap64 --dry-run  # parse + chunk only, print stats
  python -m app.ingest --only kau_pop_2016                   # one document
"""

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pymupdf
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.utils import get_tokenizer

from app.config import CHUNK_CONFIGS, settings

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources.csv"
RAW = ROOT / "data" / "raw"
MIN_CHARS_PER_PAGE = 200  # below this on average, the PDF is probably a scan with no text layer
# shortcut: v1 is English-only (the embedding model is English), so mostly non-Latin chunks are
# skipped. Upgrade with the multilingual model in PLAN.md section 13.
MIN_ASCII_SHARE = 0.8


def is_mostly_english(text: str) -> bool:
    return sum(c.isascii() for c in text) / len(text) >= MIN_ASCII_SHARE


@dataclass
class Chunk:
    page: int  # 1-based
    index: int
    text: str
    token_count: int


def read_pages(pdf_path: Path) -> list[str]:
    with pymupdf.open(pdf_path) as doc:
        return [page.get_text() for page in doc]


def _line_key(line: str) -> str:
    # Page numbers change on every page; normalise digits so "Page 12" == "Page 13".
    return re.sub(r"\d+", "#", line.strip().lower())


def clean_pages(pages: list[str]) -> list[str]:
    """Drop repeated headers/footers, re-join hyphenated words, collapse whitespace."""
    seen = Counter()
    for text in pages:
        seen.update({_line_key(ln) for ln in text.splitlines() if ln.strip()})
    threshold = len(pages) * 0.5
    repeated = {k for k, n in seen.items() if n > threshold} if len(pages) >= 4 else set()

    cleaned = []
    for text in pages:
        lines = [ln for ln in text.splitlines() if ln.strip() and _line_key(ln) not in repeated]
        joined = "\n".join(lines)
        # "fertil-\nizer" -> "fertilizer", but keep "September-\nDecember"
        joined = re.sub(r"(\w)-\n([a-z])", r"\1\2", joined)
        joined = re.sub(r"[ \t]+", " ", joined)
        joined = re.sub(r"\n{2,}", "\n", joined)
        cleaned.append(joined.strip())
    return cleaned


def chunk_pages(pages: list[str], size: int, overlap: int) -> list[Chunk]:
    # Pages are split separately so every chunk maps to exactly one page for citations.
    splitter = SentenceSplitter(chunk_size=size, chunk_overlap=overlap)
    tokenizer = get_tokenizer()
    chunks: list[Chunk] = []
    for page_no, text in enumerate(pages, start=1):
        if not text:
            continue
        for piece in splitter.split_text(text):
            piece = piece.strip()
            if piece and is_mostly_english(piece):
                chunks.append(Chunk(page_no, len(chunks), piece, len(tokenizer(piece))))
    return chunks


def load_sources(only: str | None) -> list[dict]:
    with SOURCES.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if only is None or r["doc_id"] == only]


@cache
def _model():
    from sentence_transformers import SentenceTransformer  # slow import; only when needed

    return SentenceTransformer(settings.embed_model)


def embed(texts: list[str]):
    return _model().encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=True)


def store(conn, row: dict, page_count: int, chunks: list[Chunk], vectors, config: str) -> None:
    with conn.transaction():
        conn.execute(
            """INSERT INTO documents (id, title, publisher, url, category, page_count)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, publisher = EXCLUDED.publisher,
                 url = EXCLUDED.url, category = EXCLUDED.category,
                 page_count = EXCLUDED.page_count, ingested_at = now()""",
            (row["doc_id"], row["title"], row["publisher"], row["url"], row["category"], page_count),
        )
        # Idempotent re-runs: replace this document's chunks for this config only.
        conn.execute(
            "DELETE FROM chunks WHERE document_id = %s AND config = %s", (row["doc_id"], config)
        )
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO chunks (document_id, page_start, page_end, chunk_index, text,
                                       token_count, embedding, config)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (row["doc_id"], c.page, c.page, c.index, c.text, c.token_count, v, config)
                    for c, v in zip(chunks, vectors)
                ],
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="size512_overlap64", choices=CHUNK_CONFIGS)
    ap.add_argument("--only", help="ingest a single doc_id")
    ap.add_argument("--dry-run", action="store_true", help="parse and chunk only; no embedding, no DB")
    args = ap.parse_args()
    size, overlap = CHUNK_CONFIGS[args.config]

    conn = None
    if not args.dry_run:
        from app.db import connect

        conn = connect()

    total = 0
    for row in load_sources(args.only):
        pdf = RAW / f"{row['doc_id']}.pdf"
        if not pdf.exists():
            print(f"missing {row['doc_id']}: run scripts/download.py first")
            continue
        raw_pages = read_pages(pdf)
        avg_chars = sum(map(len, raw_pages)) / max(len(raw_pages), 1)
        if avg_chars < MIN_CHARS_PER_PAGE:
            print(f"skip    {row['doc_id']}: {avg_chars:.0f} chars/page, likely scanned (no text layer)")
            continue
        chunks = chunk_pages(clean_pages(raw_pages), size, overlap)
        if not chunks:
            print(f"skip    {row['doc_id']}: no text after cleaning")
            continue
        tokens = [c.token_count for c in chunks]
        print(
            f"{row['doc_id']}: {len(raw_pages)} pages -> {len(chunks)} chunks "
            f"(tokens min {min(tokens)}, avg {sum(tokens) // len(tokens)}, max {max(tokens)})"
        )
        total += len(chunks)
        if conn is not None:
            store(conn, row, len(raw_pages), chunks, embed([c.text for c in chunks]), args.config)

    print(f"total chunks: {total}" + (" (dry run, nothing stored)" if args.dry_run else ""))
    if conn is not None:
        conn.close()


if __name__ == "__main__":
    main()
