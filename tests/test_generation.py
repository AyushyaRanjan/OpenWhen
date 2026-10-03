"""Tests for the shared generation logic and the editable prompts."""

from __future__ import annotations

import numpy as np

from app import db, generation, ollama_client, prompts


def test_prompts_load_real_files():
    lead = prompts.load("lead_in")
    step = prompts.load("tiny_step")
    assert lead.strip()
    assert step.strip()
    assert lead != step


def test_prompts_pick_up_edits_without_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(prompts, "PROMPTS_DIR", tmp_path)
    path = tmp_path / "lead_in.txt"
    path.write_text("first version", encoding="utf-8")
    assert prompts.load("lead_in") == "first version"
    path.write_text("second version", encoding="utf-8")
    assert prompts.load("lead_in") == "second version"


def test_prompts_fall_back_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(prompts, "PROMPTS_DIR", tmp_path)
    # Nothing written: must still return a non-empty, safe prompt.
    assert prompts.load("lead_in").strip()
    assert prompts.load("tiny_step").strip()


def test_build_lead_context_uses_only_provided_items():
    messages = [{"sender": "Dagger", "text": "you are not alone"}]
    wins = [{"text": "got out of bed"}]
    context = generation.build_lead_context(messages, wins)
    assert "Dagger: you are not alone" in context
    assert "got out of bed" in context
    # Nothing invented beyond the given lines.
    assert len([ln for ln in context.splitlines() if ln.startswith("- ")]) == 2


def test_build_lead_context_empty():
    assert generation.build_lead_context([], []) == "No specific items found."


async def test_generate_lead_passes_prompt_context_and_model(monkeypatch):
    captured: dict = {}

    async def fake_chat(**kwargs):
        captured.update(kwargs)
        return "  here is a warm line.  "

    monkeypatch.setattr(ollama_client, "chat", fake_chat)

    messages = [{"sender": "A", "text": "thinking of you"}]
    result = await generation.generate_lead(messages, [], model="some-model")

    assert result == "here is a warm line."
    assert captured["system"] == prompts.load("lead_in")
    assert "thinking of you" in captured["user"]
    assert captured["model"] == "some-model"
    assert captured["max_tokens"] == generation.LEAD_MAX_TOKENS


async def test_generate_step_uses_tiny_step_prompt(monkeypatch):
    captured: dict = {}

    async def fake_chat(**kwargs):
        captured.update(kwargs)
        return "one tiny thing."

    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    result = await generation.generate_step("too much to do", model="m")

    assert result == "one tiny thing."
    assert captured["system"] == prompts.load("tiny_step")
    assert captured["user"] == "too much to do"
    assert captured["model"] == "m"


async def test_gather_items_is_read_only(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    with db.connect(db_path) as conn:
        db.insert_item(
            conn,
            item_id="m1",
            kind="message",
            sender="A",
            text="you matter",
            emb=np.array([1.0, 0.0], dtype=np.float32),
            created=1000.0,
        )
        db.insert_item(
            conn,
            item_id="w1",
            kind="win",
            sender="me",
            text="made tea",
            emb=np.array([1.0, 0.0], dtype=np.float32),
            created=2000.0,
        )

    async def fake_embed(text: str):
        return np.array([1.0, 0.0], dtype=np.float32)

    monkeypatch.setattr(ollama_client, "embed", fake_embed)

    with db.connect(db_path) as conn:
        before = conn.execute("SELECT COUNT(*) AS c FROM items").fetchone()["c"]

    items = await generation.gather_items("lonely", "long night")

    with db.connect(db_path) as conn:
        after = conn.execute("SELECT COUNT(*) AS c FROM items").fetchone()["c"]

    assert before == after == 2
    assert any(m["id"] == "m1" for m in items["messages"])
    assert any(w["id"] == "w1" for w in items["wins"])
