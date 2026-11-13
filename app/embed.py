from functools import cache

from app.config import settings

# bge models expect this prefix on queries (not on passages).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@cache
def _model():
    from sentence_transformers import SentenceTransformer  # slow import; only when needed

    return SentenceTransformer(settings.embed_model)


def embed(texts: list[str], progress: bool = False):
    return _model().encode(
        texts, batch_size=64, normalize_embeddings=True, show_progress_bar=progress
    )


def embed_query(question: str):
    return embed([QUERY_PREFIX + question])[0]
