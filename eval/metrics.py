"""Pure scoring functions. Evidence and hits are compared by (document_id, page)."""

import math


def _key(x: dict) -> tuple[str, int]:
    return (x.get("doc_id") or x["document_id"], int(x["page"]))


def evidence_recall(evidence: list[dict], hits: list[dict], k: int) -> float:
    """Share of the evidence pages that appear in the top-k hits (1.0 = all found)."""
    if not evidence:
        raise ValueError("evidence_recall needs at least one evidence page")
    found = {_key(h) for h in hits[:k]}
    return sum(_key(e) in found for e in evidence) / len(evidence)


def reciprocal_rank(evidence: list[dict], hits: list[dict], k: int = 10) -> float:
    """1/rank of the first hit on any evidence page; 0 if none in the top k."""
    wanted = {_key(e) for e in evidence}
    for rank, h in enumerate(hits[:k], start=1):
        if _key(h) in wanted:
            return 1.0 / rank
    return 0.0


def citation_hit(evidence: list[dict], citations: list[dict]) -> bool:
    """True if at least one cited source is an evidence page."""
    wanted = {_key(e) for e in evidence}
    return any(_key(c) in wanted for c in citations)


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile (p in 0-100)."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")
