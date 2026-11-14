import pytest

from app import generate

CHUNKS = [
    {"id": 10, "document_id": "kau", "title": "KAU PoP", "page": 198, "url": "u1", "text": "a"},
    {"id": 11, "document_id": "pmfby", "title": "PMFBY", "page": 12, "url": "u2", "text": "b"},
]


def test_valid_citations_kept_and_mapped_in_order():
    text, cites = generate.parse_citations("Use 3 kg [2]. Sow in May [1, 2].", CHUNKS)
    assert text == "Use 3 kg [2]. Sow in May [1, 2]."
    assert [(c["n"], c["document_id"], c["page"]) for c in cites] == [(2, "pmfby", 12), (1, "kau", 198)]


def test_invalid_citation_numbers_are_dropped():
    text, cites = generate.parse_citations("Claim one [7]. Claim two [1, 9].", CHUNKS)
    assert text == "Claim one. Claim two [1]."
    assert [c["n"] for c in cites] == [1]


def test_fullwidth_brackets_are_accepted():
    text, cites = generate.parse_citations("Sow in May【2】.", CHUNKS)
    assert text == "Sow in May[2]." and [c["n"] for c in cites] == [2]


def test_dagger_locators_are_stripped():
    text, cites = generate.parse_citations("Within 48 hours[2†21.4.6.1] and 7 days【1†L5-L9】.", CHUNKS)
    assert text == "Within 48 hours[2] and 7 days[1]." and [c["n"] for c in cites] == [2, 1]


def test_prompt_numbers_sources_with_title_and_page():
    prompt = generate.build_prompt("Seed rate?", CHUNKS)
    assert "[1] (KAU PoP, p.198)\na" in prompt and "[2] (PMFBY, p.12)\nb" in prompt
    assert prompt.endswith("Question: Seed rate?")


@pytest.fixture
def fake_retrieval(monkeypatch):
    monkeypatch.setattr(generate, "retrieve", lambda q, mode: CHUNKS)


@pytest.mark.parametrize("reply", ["NOT_FOUND", " not_found. "])
def test_not_found_reply(monkeypatch, fake_retrieval, reply):
    monkeypatch.setattr(generate, "complete", lambda system, user: reply)
    result = generate.answer("Price of gold?")
    assert result == {"answer": generate.NOT_FOUND_ANSWER, "found": False, "citations": [], "uncited": False}


def test_answer_without_citations_is_flagged(monkeypatch, fake_retrieval):
    monkeypatch.setattr(generate, "complete", lambda system, user: "Sow in May.")
    result = generate.answer("When to sow?")
    assert result["found"] and result["uncited"] and result["citations"] == []


def test_no_chunks_means_not_found_without_calling_llm(monkeypatch):
    monkeypatch.setattr(generate, "retrieve", lambda q, mode: [])
    monkeypatch.setattr(generate, "complete", lambda *a: pytest.fail("LLM should not be called"))
    assert generate.answer("anything")["found"] is False
