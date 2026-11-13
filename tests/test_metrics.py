import math

import pytest

from eval.metrics import citation_hit, evidence_recall, mean, percentile, reciprocal_rank

EV = [{"doc_id": "kau", "page": 198}]
EV2 = [{"doc_id": "kau", "page": 168}, {"doc_id": "kau", "page": 175}]


def hits(*pages, doc="kau"):
    return [{"document_id": doc, "page": p} for p in pages]


def test_recall_single_evidence():
    assert evidence_recall(EV, hits(5, 198, 7), k=5) == 1.0
    assert evidence_recall(EV, hits(5, 6, 7, 8, 9, 198), k=5) == 0.0  # outside top 5


def test_recall_multi_hop_counts_each_page():
    assert evidence_recall(EV2, hits(168, 1, 2), k=5) == 0.5
    assert evidence_recall(EV2, hits(175, 168), k=5) == 1.0


def test_recall_same_page_different_doc_is_a_miss():
    assert evidence_recall(EV, hits(198, doc="tnau"), k=5) == 0.0


def test_recall_rejects_empty_evidence():
    with pytest.raises(ValueError):
        evidence_recall([], hits(1), k=5)


def test_reciprocal_rank():
    assert reciprocal_rank(EV, hits(1, 2, 198)) == pytest.approx(1 / 3)
    assert reciprocal_rank(EV, hits(1, 2)) == 0.0
    assert reciprocal_rank(EV2, hits(9, 175, 168)) == 0.5  # first relevant wins


def test_citation_hit():
    assert citation_hit(EV, [{"document_id": "kau", "page": 198, "n": 1}])
    assert not citation_hit(EV, [{"document_id": "kau", "page": 199, "n": 1}])
    assert not citation_hit(EV, [])


def test_percentile_and_mean():
    assert percentile([5, 1, 3, 2, 4], 50) == 3
    assert percentile([5, 1, 3, 2, 4], 95) == 5
    assert math.isnan(percentile([], 50)) and math.isnan(mean([]))
    assert mean([1, 2, 3]) == 2
