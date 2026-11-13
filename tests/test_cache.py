from fastapi.testclient import TestClient

from app import cache, main

client = TestClient(main.app)

RESULT = {"answer": "Use 3 to 4 kg [1].", "found": True, "uncited": False, "citations": []}


def counting_answer(monkeypatch):
    calls = []

    def fake(q, mode):
        calls.append(q)
        return RESULT

    monkeypatch.setattr(main.generate, "answer", fake)
    return calls


def test_second_identical_question_is_served_from_cache(monkeypatch):
    calls = counting_answer(monkeypatch)
    first = client.post("/ask", json={"question": "Seed rate for bottle gourd?"}).json()
    second = client.post("/ask", json={"question": "  seed rate for BOTTLE gourd  "}).json()
    assert len(calls) == 1
    assert (first["cached"], second["cached"]) == (False, True)
    assert second["answer"] == RESULT["answer"]


def test_cache_key_changes_with_mode_and_model(monkeypatch):
    base = cache.answer_key("Seed rate?", "hybrid_rerank")
    assert cache.answer_key("seed rate", "hybrid_rerank") == base
    assert cache.answer_key("Seed rate?", "vector") != base
    monkeypatch.setattr(cache.settings, "llm_model", "another-model")
    assert cache.answer_key("Seed rate?", "hybrid_rerank") != base


def test_cache_entries_expire_after_a_week(fake_redis, monkeypatch):
    counting_answer(monkeypatch)
    client.post("/ask", json={"question": "Seed rate for okra?"})
    answer_ttls = [t for k, t in fake_redis.ttl.items() if k.startswith("answer:")]
    assert answer_ttls == [7 * 24 * 3600]


def test_rate_limit_blocks_after_the_hourly_quota(monkeypatch):
    counting_answer(monkeypatch)
    monkeypatch.setattr(cache.settings, "rate_limit_per_hour", 2)
    codes = [client.post("/ask", json={"question": f"Question {i}?"}).status_code for i in range(3)]
    assert codes == [200, 200, 429]


def test_rate_limit_zero_disables_it(monkeypatch):
    counting_answer(monkeypatch)
    monkeypatch.setattr(cache.settings, "rate_limit_per_hour", 0)
    assert all(
        client.post("/ask", json={"question": f"Q number {i}"}).status_code == 200
        for i in range(5)
    )


def test_redis_down_fails_open(fake_redis, monkeypatch):
    calls = counting_answer(monkeypatch)
    fake_redis.down = True
    r = client.post("/ask", json={"question": "Seed rate for bottle gourd?"})
    assert r.status_code == 200 and r.json()["cached"] is False and len(calls) == 1
    assert cache.ping() is False


def test_health_reports_redis(fake_redis, monkeypatch):
    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql):
            return None

    monkeypatch.setattr(main, "connect", Conn)
    assert client.get("/health").json() == {"db": "ok", "redis": "ok"}
    fake_redis.down = True
    assert client.get("/health").json() == {"db": "ok", "redis": "down"}
