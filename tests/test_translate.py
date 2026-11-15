from app import translate
from app.llm import LLMError


def test_english_questions_are_not_translated(monkeypatch):
    monkeypatch.setattr(translate, "complete", lambda *a: (_ for _ in ()).throw(AssertionError))
    assert (
        translate.search_query.__wrapped__("Seed rate for bottle gourd?")
        == "Seed rate for bottle gourd?"
    )


def test_hindi_question_is_translated(monkeypatch):
    monkeypatch.setattr(translate, "complete", lambda system, q: ' "Seed rate for bottle gourd?" ')
    assert translate.search_query.__wrapped__("लौकी के बीज कितने?") == "Seed rate for bottle gourd?"


def test_translation_failure_falls_back_to_original(monkeypatch):
    def boom(*a):
        raise LLMError("down")

    monkeypatch.setattr(translate, "complete", boom)
    assert translate.search_query.__wrapped__("लौकी के बीज कितने?") == "लौकी के बीज कितने?"


def test_mixed_text_detection():
    assert translate.is_mostly_english("PM-KISAN eligibility?")
    assert not translate.is_mostly_english("पीएम-किसान पात्रता?")
