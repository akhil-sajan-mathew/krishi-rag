import pytest

from app import decompose, retrieve


@pytest.fixture(autouse=True)
def clear_caches():
    decompose.sub_queries.cache_clear()


def test_single_topic_question_skips_llm(monkeypatch):
    monkeypatch.setattr(decompose, "complete", lambda *a: pytest.fail("LLM should not be called"))
    assert decompose.sub_queries("What is the seed rate for bottle gourd?") == (
        "What is the seed rate for bottle gourd?",
    )


def test_compound_question_is_split(monkeypatch):
    monkeypatch.setattr(
        decompose,
        "complete",
        lambda s, q: "- cocoa compost per pit\n- dried cocoa bean moisture\n- extra",
    )
    assert decompose.sub_queries("For cocoa, compost per pit and bean moisture?") == (
        "cocoa compost per pit",
        "dried cocoa bean moisture",
    )


def test_llm_failure_falls_back_to_one_search(monkeypatch):
    def boom(*a):
        raise decompose.LLMError("down")

    monkeypatch.setattr(decompose, "complete", boom)
    assert decompose.sub_queries("A and B?") == ("A and B?",)


def test_split_retrieval_interleaves_and_dedupes(monkeypatch):
    results = {
        "q1": [{"id": 1}, {"id": 2}, {"id": 3}],
        "q2": [{"id": 1}, {"id": 4}, {"id": 5}],
    }
    monkeypatch.setattr(retrieve, "sub_queries", lambda q: ("q1", "q2"))
    monkeypatch.setattr(retrieve, "search_query", lambda q: q)
    monkeypatch.setattr(retrieve, "_retrieve_one", lambda q, mode, n, config: results[q][:n])
    assert [c["id"] for c in retrieve.retrieve("orig")] == [1, 2, 4, 3, 5]
