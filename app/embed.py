from functools import cache

# (query prefix, passage prefix) each model was trained with. Wrong prefixes quietly hurt recall.
PREFIXES = {
    "BAAI/bge-small-en-v1.5": ("Represent this sentence for searching relevant passages: ", ""),
    "intfloat/multilingual-e5-small": ("query: ", "passage: "),
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": ("", ""),
}


@cache
def _model(name: str):
    from sentence_transformers import SentenceTransformer  # slow import; only when needed

    return SentenceTransformer(name)


def _encode(texts: list[str], model: str, progress: bool = False):
    return _model(model).encode(
        texts, batch_size=64, normalize_embeddings=True, show_progress_bar=progress
    )


def embed_passages(texts: list[str], model: str, progress: bool = False):
    prefix = PREFIXES[model][1]
    return _encode([prefix + t for t in texts], model, progress)


def embed_query(question: str, model: str):
    return _encode([PREFIXES[model][0] + question], model)[0]
