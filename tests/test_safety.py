"""Crisis/safety tests. 15+ tests covering keywords, obfuscation, negatives,
and the "keyword triggers -> model never called" guarantee.
"""

from __future__ import annotations

from app import safety


def test_empty_is_not_crisis():
    assert not safety.is_crisis("")
    assert not safety.is_crisis("   ")


def test_sad_but_not_crisis():
    assert not safety.is_crisis("I'm feeling really low today")
    assert not safety.is_crisis("Life is hard sometimes")
    assert not safety.is_crisis("I had a rough day")
    assert not safety.is_crisis("Tired, that's all")


def test_basic_suicide_phrases():
    assert safety.is_crisis("I want to die")
    assert safety.is_crisis("i want to die")
    assert safety.is_crisis("I WANT TO DIE")


def test_common_variants():
    assert safety.is_crisis("wanna die")
    assert safety.is_crisis("dont wanna live")
    assert safety.is_crisis("don't want to live")
    assert safety.is_crisis("do not want to live")
    assert safety.is_crisis("better off dead")
    assert safety.is_crisis("no reason to live")


def test_self_harm_phrases():
    assert safety.is_crisis("hurt myself")
    assert safety.is_crisis("cut myself")
    assert safety.is_crisis("cutting myself")
    assert safety.is_crisis("overdose")
    assert safety.is_crisis("took too many pills")


def test_repeated_punctuation():
    assert safety.is_crisis("I want to die!!!")
    assert safety.is_crisis("kill myself???")


def test_repeated_letters():
    assert safety.is_crisis("waaaaant to die")
    assert safety.is_crisis("kiiiill myself")


def test_extra_whitespace():
    assert safety.is_crisis("   want   to   die   ")
    assert safety.is_crisis("want\nto\ndie")
    assert safety.is_crisis("want\tto\t die")


def test_mixed_obfuscation():
    assert safety.is_crisis("I waaant to diiiie!!!")
    assert safety.is_crisis("  don't   wannaaa   liiivvveee  ")


def test_partial_should_not_trigger():
    assert not safety.is_crisis("I want to diet")
    assert not safety.is_crisis("I died laughing")
    assert not safety.is_crisis("self improvement")


def test_burden_phrases():
    assert safety.is_crisis("I'm a burden")
    assert safety.is_crisis("burden on everyone")
    assert safety.is_crisis("no one would miss me")


def test_thinking_about():
    assert safety.is_crisis("thought about killing")
    assert safety.is_crisis("been thinking about dying")


def test_crisis_response_contains_resources():
    r = safety.crisis_response()
    assert r["type"] == "crisis"
    assert "14416" in r["message"]
    assert "112" in r["message"]
    assert r["tel"]["telemanas_14416"] == "tel:14416"
    assert r["tel"]["emergency_112"] == "tel:112"
    assert "resources" in r and len(r["resources"]) >= 3


def test_keyword_triggers_before_model(monkeypatch):
    """When keyword layer triggers, Ollama must never be called."""
    called = {"n": 0}

    async def fake_chat(*args, **kwargs):
        called["n"] += 1
        return {"content": "NO"}

    # Patch the chat used by safety module
    monkeypatch.setattr(safety, "chat", fake_chat)

    # Should return True from keywords, never hit chat
    result = safety.check("kill myself")
    assert result is True
    assert called["n"] == 0


def test_model_only_when_keyword_okay_and_enabled(monkeypatch):
    called = {"n": 0}

    async def fake_chat(*args, **kwargs):
        called["n"] += 1
        return {"content": "YES"}

    monkeypatch.setattr(safety, "chat", fake_chat)
    monkeypatch.setattr(safety.settings, "use_model_safety_check", True)

    result = safety.check("feeling very hopeless right now")
    assert result is True
    assert called["n"] == 1


def test_model_returns_no_on_unclear(monkeypatch):
    called = {"n": 0}

    async def fake_chat(*args, **kwargs):
        called["n"] += 1
        return {"content": "MAYBE"}

    monkeypatch.setattr(safety, "chat", fake_chat)
    monkeypatch.setattr(safety.settings, "use_model_safety_check", True)

    result = safety.check("feeling very hopeless right now")
    assert result is False
    assert called["n"] == 1


def test_model_failure_treated_as_no(monkeypatch):
    called = {"n": 0}

    async def fake_chat(*args, **kwargs):
        called["n"] += 1
        raise RuntimeError("ollama down")

    monkeypatch.setattr(safety, "chat", fake_chat)
    monkeypatch.setattr(safety.settings, "use_model_safety_check", True)

    result = safety.check("feeling very hopeless right now")
    assert result is False
    assert called["n"] == 1


def test_model_disabled_skips_second_pass(monkeypatch):
    called = {"n": 0}

    async def fake_chat(*args, **kwargs):
        called["n"] += 1
        return {"content": "YES"}

    monkeypatch.setattr(safety, "chat", fake_chat)
    monkeypatch.setattr(safety.settings, "use_model_safety_check", False)

    result = safety.check("feeling very hopeless right now")
    assert result is False
    assert called["n"] == 0
