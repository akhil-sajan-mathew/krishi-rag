"""Split a question about two different things into two search queries, so each gets its own search."""

import logging
from functools import lru_cache

from app.llm import LLMError, complete

log = logging.getLogger("krishi.decompose")
MAX_QUERIES = 2

SYSTEM = f"""If the farmer's question asks about two or more DIFFERENT topics (different crops, pests,
schemes or rules), split it into at most {MAX_QUERIES} self-contained search queries, one per line,
each keeping its crop or scheme name. If it is about one topic (even with several details), reply
with the question unchanged on one line. Reply with the queries only, no numbering."""


def looks_compound(question: str) -> bool:
    # shortcut: cheap gate so single-topic questions skip the extra LLM call; misses "also"-style phrasings.
    return " and " in question.lower() or any(c in question for c in ",;")


@lru_cache(maxsize=1024)
def sub_queries(question: str) -> tuple[str, ...]:
    if not looks_compound(question):
        return (question,)
    try:
        lines = complete(SYSTEM, question).strip().splitlines()
    except LLMError as e:
        log.warning("question splitting failed, searching as one: %s", e)
        return (question,)
    queries = tuple(dict.fromkeys(q.strip().lstrip("-*• ").strip() for q in lines if q.strip()))
    return queries[:MAX_QUERIES] or (question,)
