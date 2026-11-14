import pytest

from app import embed
from app.config import BGE_EN, CHUNK_CONFIGS, E5_MULTI


@pytest.fixture
def seen(monkeypatch):
    texts = []

    def fake_encode(batch, model, progress=False):
        texts.extend(batch)
        return [[0.0]] * len(batch)

    monkeypatch.setattr(embed, "_encode", fake_encode)
    return texts


def test_e5_gets_query_and_passage_prefixes(seen):
    embed.embed_query("seed rate?", E5_MULTI)
    embed.embed_passages(["Seed rate is 3 kg."], E5_MULTI)
    assert seen == ["query: seed rate?", "passage: Seed rate is 3 kg."]


def test_bge_prefixes_queries_only(seen):
    embed.embed_query("seed rate?", BGE_EN)
    embed.embed_passages(["Seed rate is 3 kg."], BGE_EN)
    assert seen[0].startswith("Represent this sentence") and seen[1] == "Seed rate is 3 kg."


def test_every_configured_model_has_prefixes():
    assert {model for _, _, model in CHUNK_CONFIGS.values()} <= set(embed.PREFIXES)
