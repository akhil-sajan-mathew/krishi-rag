import pytest
from fastapi.testclient import TestClient

from app import llm, main

client = TestClient(main.app)

RESULT = {
    "answer": "Use 3 to 4 kilograms per hectare [1].",
    "found": True,
    "uncited": False,
    "citations": [{"n": 1, "document_id": "kau", "title": "KAU PoP", "page": 198, "url": None}],
}


@pytest.mark.parametrize(
    "body", [{"question": "hi"}, {"question": "x" * 501}, {"question": "ok?", "mode": "magic"}, {}]
)
def test_bad_input_is_rejected(body):
    assert client.post("/ask", json=body).status_code == 422


def test_ask_returns_answer_with_citations(monkeypatch):
    monkeypatch.setattr(main.generate, "answer", lambda q, mode: RESULT)
    r = client.post("/ask", json={"question": "  Seed rate for bottle gourd?  "})
    assert r.status_code == 200
    body = r.json()
    assert body["citations"][0]["page"] == 198 and body["mode"] == "hybrid_rerank"
    assert isinstance(body["latency_ms"], int)


def test_llm_failure_returns_503(monkeypatch):
    def boom(q, mode):
        raise llm.LLMError("LLM_MODEL is not set in .env")

    monkeypatch.setattr(main.generate, "answer", boom)
    r = client.post("/ask", json={"question": "Seed rate?"})
    assert r.status_code == 503 and "LLM_MODEL" in r.json()["detail"]


def test_missing_model_gives_clear_error(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_model", "")
    with pytest.raises(llm.LLMError, match="LLM_MODEL is not set"):
        llm.complete("s", "u")


def test_unknown_provider_gives_clear_error(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_provider", "nope")
    with pytest.raises(llm.LLMError, match="LLM_PROVIDER must be one of"):
        llm.complete("s", "u")
