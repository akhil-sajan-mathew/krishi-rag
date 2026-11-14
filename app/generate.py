"""Turn retrieved chunks into a cited answer. Citations are prompt-based, so any LLM works."""

import re

from app.llm import complete
from app.retrieve import Mode, retrieve

NOT_FOUND = "NOT_FOUND"
NOT_FOUND_ANSWER = "The documents I have don't cover this question."

SYSTEM = f"""You answer farmers' questions using ONLY the numbered sources provided.
Rules:
- Put the source number in square brackets after each claim, like [2]. Cite only numbers that exist.
- If the sources answer only part of the question, answer that part and say plainly which part
  the documents do not cover.
- Only if the sources contain nothing that answers any part of the question, reply with exactly
  {NOT_FOUND} and nothing else.
- Under 150 words. Plain, simple language. Write units in full (kilograms per hectare, not kg ha-1).
- Do not use outside knowledge."""


def build_prompt(question: str, chunks: list[dict]) -> str:
    sources = "\n\n".join(
        f"[{i}] ({c['title']}, p.{c['page']})\n{c['text']}" for i, c in enumerate(chunks, start=1)
    )
    return f"Sources:\n\n{sources}\n\nQuestion: {question}"


def parse_citations(text: str, chunks: list[dict]) -> tuple[str, list[dict]]:
    """Keep [n] markers that point at a real source, strip the rest, list cited sources in order."""
    valid = range(1, len(chunks) + 1)
    cited: list[int] = []
    text = text.translate(str.maketrans("【】", "[]"))  # some models (gpt-oss) cite as 【n】

    def keep(m: re.Match) -> str:
        good = [n for n in map(int, re.findall(r"\d+", m.group(1))) if n in valid]
        cited.extend(n for n in good if n not in cited)
        return f"[{', '.join(map(str, good))}]" if good else ""

    # gpt-oss may append its own locator: [2†21.4.6.1]. Keep the number, drop the locator.
    cleaned = re.sub(r"\[(\d+(?:\s*,\s*\d+)*)(?:†[^\]]*)?\]", keep, text)
    cleaned = re.sub(r"[ \t]+([.,;:])", r"\1", re.sub(r"[ \t]{2,}", " ", cleaned)).strip()
    citations = [
        {k: chunks[n - 1][k] for k in ("document_id", "title", "page", "url")} | {"n": n}
        for n in cited
    ]
    return cleaned, citations


def _not_found() -> dict:
    return {"answer": NOT_FOUND_ANSWER, "found": False, "citations": [], "uncited": False}


def answer(question: str, mode: Mode = "hybrid_rerank") -> dict:
    return answer_from_chunks(question, retrieve(question, mode))


def answer_from_chunks(question: str, chunks: list[dict]) -> dict:
    if not chunks:
        return _not_found()
    raw = complete(SYSTEM, build_prompt(question, chunks))
    if raw.strip().strip(".").upper() == NOT_FOUND:
        return _not_found()
    text, citations = parse_citations(raw, chunks)
    return {"answer": text, "found": True, "citations": citations, "uncited": not citations}
