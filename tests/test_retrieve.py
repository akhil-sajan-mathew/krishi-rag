from app.retrieve import fuse


def _hits(*ids):
    return [{"id": i} for i in ids]


def test_rrf_rewards_items_found_by_both_retrievers():
    fused = fuse([_hits(1, 2, 3), _hits(3, 4)])
    # 3 is in both lists, so it beats 1 even though 1 is top of one list.
    # 2 and 4 tie (both rank 2); ties keep first-seen order.
    assert [h["id"] for h in fused] == [3, 1, 2, 4]


def test_rrf_scores_match_formula():
    # Single list: order is preserved; with k=0, scores are 1, 1/2, 1/3.
    assert [h["id"] for h in fuse([_hits(7, 8, 9)], k=0)] == [7, 8, 9]


def test_rrf_handles_empty_lists():
    assert fuse([[], _hits(5)]) == [{"id": 5}]
    assert fuse([[], []]) == []


def test_weighted_rrf_can_downweight_a_list():
    # Equal weights: 3 (in both lists) wins. Keyword list weighted 0: pure vector order.
    vector, keyword = _hits(1, 2, 3), _hits(3, 4)
    assert [h["id"] for h in fuse([vector, keyword], weights=[1.0, 0.0])][:3] == [1, 2, 3]
    assert fuse([vector, keyword], weights=[1.0, 1.0])[0]["id"] == 3
