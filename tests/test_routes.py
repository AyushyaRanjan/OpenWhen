"""Route tests with mocked Ollama."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import main, ollama_client, safety


def test_create_and_list_item(tmp_path, monkeypatch):
    # Redirect media/db to tmp
    from dataclasses import replace

    from app import config, db, routes
    from app.config import BASE_DIR

    db_path = tmp_path / "t.db"
    media_dir = tmp_path / "media"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setattr(routes.items, "MEDIA_DIR", media_dir)
    # Listing is admin-only now, so give the test a passcode to present.
    monkeypatch.setattr(
        config, "settings", replace(config.settings, admin_passcode="test-pass")
    )

    async def fake_embed(text: str):
        import numpy as np

        return np.array([0.1, 0.2], dtype=np.float32)

    monkeypatch.setattr(ollama_client, "embed", fake_embed)

    client = TestClient(main.app)
    r = client.post(
        "/api/item",
        data={"kind": "message", "sender": "Dagger", "text": "hi", "mood": "lonely"},
    )
    assert r.status_code == 200
    j = r.json()
    assert "id" in j

    r = client.get("/api/items?kind=message", headers={"X-Admin-Passcode": "test-pass"})
    assert r.status_code == 200
    items_list = r.json()
    assert len(items_list) == 1
    assert items_list[0]["text"] == "hi"
    assert "emb" not in items_list[0]


def test_feel_crisis_blocks_model(tmp_path, monkeypatch):
    from app import db, routes

    db_path = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    called = {"n": 0}

    async def fake_embed(*a, **k):
        called["n"] += 1
        import numpy as np

        return np.array([0.1], dtype=np.float32)

    async def fake_chat(*a, **k):
        called["n"] += 10
        return "should not happen"

    monkeypatch.setattr(ollama_client, "embed", fake_embed)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)

    client = TestClient(main.app)
    r = client.post("/api/feel", json={"mood": "sad", "text": "kill myself"})
    assert r.status_code == 200
    j = r.json()
    assert j["crisis"] is True
    assert "14416" in j["message"]
    assert called["n"] == 0


def test_feel_fallback_when_ollama_unavailable(tmp_path, monkeypatch):
    from app import db, routes

    db_path = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    async def fake_embed(*a, **k):
        import numpy as np

        return np.array([0.1], dtype=np.float32)

    async def fake_chat(*a, **k):
        raise ollama_client.OllamaUnavailable()

    # Seed messages
    with db.connect(db_path) as conn:
        db.insert_item(conn, item_id="m1", kind="message", sender="A", text="you matter", emb=None, created=1000.0)
        db.insert_item(conn, item_id="m2", kind="message", sender="B", text="hang in", emb=None, created=2000.0)

    monkeypatch.setattr(ollama_client, "embed", fake_embed)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)

    client = TestClient(main.app)
    r = client.post("/api/feel", json={"mood": "low", "text": ""})
    assert r.status_code == 200
    j = r.json()
    assert j["crisis"] is False
    assert j["lead"] == "Here's something from someone who cares about you."
    assert len(j["messages"]) >= 1


def test_step_crisis_blocks_model(tmp_path, monkeypatch):
    called = {"n": 0}

    async def fake_chat(*a, **k):
        called["n"] += 1
        return "ok"

    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    client = TestClient(main.app)
    r = client.post("/api/step", json={"challenge": "want to die"})
    assert r.status_code == 200
    j = r.json()
    assert j["crisis"] is True
    assert called["n"] == 0


def test_win_crisis_blocks(tmp_path, monkeypatch):
    called = {"n": 0}

    async def fake_chat(*a, **k):
        called["n"] += 1
        return "ok"

    monkeypatch.setattr(ollama_client, "chat", fake_chat)
    client = TestClient(main.app)
    r = client.post("/api/win", json={"text": "kill myself"})
    assert r.status_code == 200
    j = r.json()
    assert j["crisis"] is True
    assert called["n"] == 0
