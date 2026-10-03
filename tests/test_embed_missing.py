"""Tests for the one-time win-embedding backfill tool."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from app import db, ollama_client

BASE = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "embed_missing", BASE / "tools" / "embed_missing.py"
)
assert _spec and _spec.loader
embed_missing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(embed_missing)


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    with db.connect(db_path) as conn:
        db.insert_item(
            conn, item_id="w1", kind="win", sender="me", text="a win", created=1000.0
        )
        db.insert_item(
            conn, item_id="m1", kind="message", sender="A", text="a note", created=2000.0
        )
    return db_path


async def test_backfill_embeds_only_vectorless_wins(seeded, monkeypatch):
    calls: list[str] = []

    async def fake_embed(text: str):
        calls.append(text)
        return np.array([1.0, 0.0], dtype=np.float32)

    monkeypatch.setattr(ollama_client, "embed", fake_embed)

    assert await embed_missing.backfill(seeded) == 1
    assert calls == ["a win"]

    with db.connect(seeded) as conn:
        wins = db.get_all_with_embeddings(conn, "win")
        message = conn.execute("SELECT emb FROM items WHERE id = 'm1'").fetchone()
    assert [row["id"] for row, _ in wins] == ["w1"]
    # A message stored without a vector is left alone: save-anyway notes must
    # never be handed to the model.
    assert message["emb"] is None


async def test_backfill_is_a_noop_when_everything_is_embedded(seeded, monkeypatch):
    with db.connect(seeded) as conn:
        db.update_embedding(conn, "w1", np.array([0.0, 1.0], dtype=np.float32))

    async def must_not_embed(text: str):
        raise AssertionError("nothing should be embedded")

    monkeypatch.setattr(ollama_client, "embed", must_not_embed)
    assert await embed_missing.backfill(seeded) == 0


async def test_backfill_stops_when_ollama_is_down(seeded, monkeypatch):
    async def dead_embed(*a, **k):
        raise ollama_client.OllamaUnavailable()

    monkeypatch.setattr(ollama_client, "embed", dead_embed)

    assert await embed_missing.backfill(seeded) == 0
    with db.connect(seeded) as conn:
        row = conn.execute("SELECT emb FROM items WHERE id = 'w1'").fetchone()
    assert row["emb"] is None
