"""Find the chunks most relevant to a question: vector, keyword, hybrid (RRF) and reranked."""

from functools import cache
from typing import Literal

from app.config import embed_model_for, settings
from app.db import connect
from app.embed import embed_query
from app.translate import search_query

Mode = Literal["vector", "keyword", "hybrid", "hybrid_rerank"]
MODES: tuple[Mode, ...] = ("vector", "keyword", "hybrid", "hybrid_rerank")
CANDIDATES = 20  # per retriever, before fusion

_SELECT = """SELECT c.id, c.document_id, d.title, d.url, c.page_start AS page, c.text
             FROM chunks c JOIN documents d ON d.id = c.document_id"""


def _rows(cur) -> list[dict]:
    names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def vector_search(conn, question: str, k: int, config: str) -> list[dict]:
    cur = conn.execute(
        f"{_SELECT} WHERE c.config = %s ORDER BY c.embedding <=> %s LIMIT %s",
        (config, embed_query(question, embed_model_for(config)), k),
    )
    return _rows(cur)


def keyword_search(conn, question: str, k: int, config: str) -> list[dict]:
    # OR the words: AND-ing every word of a conversational question almost never matches.
    # ts_rank_cd still ranks chunks that contain more of the words higher.
    cur = conn.execute(
        f"""{_SELECT},
                 to_tsquery('english', replace(plainto_tsquery('english', %s)::text, '&', '|')) q
            WHERE c.config = %s AND c.tsv @@ q
            ORDER BY ts_rank_cd(c.tsv, q) DESC LIMIT %s""",
        (question, config, k),
    )
    return _rows(cur)


def fuse(
    ranked_lists: list[list[dict]], k: int = 60, weights: list[float] | None = None
) -> list[dict]:
    """Weighted reciprocal rank fusion: score = sum of weight / (k + rank), rank starting at 1."""
    weights = weights or [1.0] * len(ranked_lists)
    scores: dict[int, float] = {}
    by_id: dict[int, dict] = {}
    for results, weight in zip(ranked_lists, weights, strict=True):
        for rank, hit in enumerate(results, start=1):
            scores[hit["id"]] = scores.get(hit["id"], 0.0) + weight / (k + rank)
            by_id[hit["id"]] = hit
    return [by_id[i] for i in sorted(scores, key=scores.get, reverse=True)]


@cache
def _reranker():
    from sentence_transformers import CrossEncoder  # slow import; only when needed

    return CrossEncoder(settings.rerank_model)


def rerank(question: str, hits: list[dict], top_n: int) -> list[dict]:
    if not hits:
        return []
    scores = _reranker().predict([(question, h["text"]) for h in hits])
    ranked = sorted(zip(hits, scores), key=lambda p: p[1], reverse=True)
    return [h for h, _ in ranked[:top_n]]


def retrieve(
    question: str, mode: Mode = "hybrid_rerank", top_n: int = 5, config: str | None = None
) -> list[dict]:
    config = config or settings.chunk_config
    question = search_query(question)  # non-English questions are searched in English
    # shortcut: one connection per call; add a pool (psycopg_pool) when traffic needs it.
    with connect() as conn:
        if mode == "vector":
            return vector_search(conn, question, top_n, config)
        if mode == "keyword":
            return keyword_search(conn, question, top_n, config)
        fused = fuse(
            [
                vector_search(conn, question, CANDIDATES, config),
                keyword_search(conn, question, CANDIDATES, config),
            ],
            weights=[1.0, settings.keyword_weight],
        )
    if mode == "hybrid":
        return fused[:top_n]
    return rerank(question, fused[: settings.rerank_pool], top_n)
