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


def test_recent_returns_messages_without_embeddings(tmp_path, monkeypatch):
    from app import db

    db_path = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    with db.connect(db_path) as conn:
        db.insert_item(conn, item_id="m1", kind="message", sender="A", text="first", created=1000.0)
        db.insert_item(conn, item_id="m2", kind="message", sender="B", text="second", created=2000.0)
        db.insert_item(conn, item_id="w1", kind="win", sender="me", text="a win", created=3000.0)

    client = TestClient(main.app)
    r = client.get("/api/recent?k=5")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    # Newest first, only notes from loved ones, never a vector.
    assert [m["text"] for m in msgs] == ["second", "first"]
    assert all(m["kind"] == "message" for m in msgs)
    assert all("emb" not in m for m in msgs)


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


def test_win_is_saved_with_a_vector_so_it_can_come_back(tmp_path, monkeypatch):
    import numpy as np

    from app import db

    db_path = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    async def fake_embed(text: str):
        return np.array([1.0, 0.0], dtype=np.float32)

    monkeypatch.setattr(ollama_client, "embed", fake_embed)

    client = TestClient(main.app)
    r = client.post("/api/win", json={"text": "made it to the shower today"})
    assert r.status_code == 200 and r.json()["ok"] is True

    with db.connect(db_path) as conn:
        rows = db.get_all_with_embeddings(conn, "win")
    assert len(rows) == 1
    assert rows[0][0]["text"] == "made it to the shower today"


def test_win_is_still_saved_when_ollama_is_down(tmp_path, monkeypatch):
    from app import db

    db_path = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    async def dead_embed(*a, **k):
        raise ollama_client.OllamaUnavailable()

    monkeypatch.setattr(ollama_client, "embed", dead_embed)

    client = TestClient(main.app)
    r = client.post("/api/win", json={"text": "got out of bed"})
    assert r.status_code == 200 and r.json()["ok"] is True

    # Their words are kept even with no vector; the backfill tool can add one.
    with db.connect(db_path) as conn:
        rows = db.list_items(conn, "win")
    assert [row["text"] for row in rows] == ["got out of bed"]
    assert rows[0]["emb"] is None


def test_feel_returns_a_win_on_a_mood_tap_alone(tmp_path, monkeypatch):
    import numpy as np

    from app import db

    db_path = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    with db.connect(db_path) as conn:
        db.insert_item(
            conn, item_id="w1", kind="win", sender="me", text="finished the form",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=1000.0,
        )

    async def fake_embed(text: str):
        return np.array([1.0, 0.0], dtype=np.float32)

    async def fake_chat(*a, **k):
        return "Something you did before."

    monkeypatch.setattr(ollama_client, "embed", fake_embed)
    monkeypatch.setattr(ollama_client, "chat", fake_chat)

    client = TestClient(main.app)
    r = client.post("/api/feel", json={"mood": "lonely", "text": ""})
    assert r.status_code == 200
    assert any(w["id"] == "w1" for w in r.json()["wins"])


def test_wins_endpoint_lists_only_wins_without_embeddings(tmp_path, monkeypatch):
    from app import db

    db_path = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    with db.connect(db_path) as conn:
        db.insert_item(conn, item_id="w1", kind="win", sender="me", text="older win", created=1000.0)
        db.insert_item(conn, item_id="m1", kind="message", sender="A", text="a note", created=2000.0)
        db.insert_item(conn, item_id="w2", kind="win", sender="me", text="newer win", created=3000.0)

    client = TestClient(main.app)
    r = client.get("/api/wins")
    assert r.status_code == 200
    got = r.json()["wins"]
    assert [w["text"] for w in got] == ["newer win", "older win"]
    assert all(w["kind"] == "win" for w in got)
    assert all("emb" not in w for w in got)
