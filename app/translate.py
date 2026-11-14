"""Turn a non-English question into an English search query, so it can use the English index."""

import logging
from functools import lru_cache

from app.llm import LLMError, complete

log = logging.getLogger("krishi.translate")
MIN_ASCII_SHARE = 0.8

SYSTEM = """Translate the farmer's question into English for searching agricultural documents.
Keep every crop, pest, disease, chemical, quantity and scheme name. Write the usual English
name of local crop names (for example लौकी -> bottle gourd, सुपारी -> arecanut).
Reply with the English question only, nothing else."""


def is_mostly_english(text: str) -> bool:
    return sum(c.isascii() for c in text) / len(text) >= MIN_ASCII_SHARE


@lru_cache(maxsize=1024)
def search_query(question: str) -> str:
    """The question itself if it's English; otherwise its English translation (or the original
    question if translation fails, so search degrades instead of erroring)."""
    if is_mostly_english(question):
        return question
    try:
        english = complete(SYSTEM, question).strip().strip('"')
    except LLMError as e:
        log.warning("query translation failed, searching with the original: %s", e)
        return question
    return english or question
