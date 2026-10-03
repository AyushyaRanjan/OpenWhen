"""Public config, admin passcode gate, and item safety tests."""

from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from app import config, main


def _set_passcode(monkeypatch, code: str) -> None:
    # Settings is frozen, so tests swap the whole object rather than mutate it.
    monkeypatch.setattr(config, "settings", replace(config.settings, admin_passcode=code))


def test_public_config_exposes_only_allowed_keys():
    client = TestClient(main.app)
    r = client.get("/api/config")
    assert r.status_code == 200
    # Pinned exactly: helper_phone, model names and the passcode must never ride along.
    assert set(r.json().keys()) == {"friend_name", "moods", "resting_message"}


def test_admin_list_locked_without_or_with_wrong_passcode(monkeypatch):
    _set_passcode(monkeypatch, "s3cret")
    client = TestClient(main.app)
    assert client.get("/api/items?kind=message").status_code == 401
    wrong = client.get("/api/items?kind=message", headers={"X-Admin-Passcode": "nope"})
    assert wrong.status_code == 401


def test_admin_locked_when_passcode_is_unset(monkeypatch):
    _set_passcode(monkeypatch, "")
    client = TestClient(main.app)
    # Empty means switched off, not open.
    r = client.get("/api/items?kind=message", headers={"X-Admin-Passcode": ""})
    assert r.status_code == 401


def test_admin_list_ok_with_passcode(monkeypatch, tmp_path):
    from app import db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    _set_passcode(monkeypatch, "s3cret")
    client = TestClient(main.app)
    r = client.get("/api/items?kind=message", headers={"X-Admin-Passcode": "s3cret"})
    assert r.status_code == 200
    assert r.json() == []


def test_admin_delete_locked_without_passcode(monkeypatch, tmp_path):
    from app import db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    _set_passcode(monkeypatch, "s3cret")
    client = TestClient(main.app)
    assert client.delete("/api/item/anything").status_code == 401


def test_crisis_text_on_item_never_calls_embed(monkeypatch, tmp_path):
    from app import db, ollama_client
    from app.routes import items as items_module

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(items_module, "MEDIA_DIR", tmp_path / "media")

    called = {"n": 0}

    async def fake_embed(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("embed must not run when the safety check trips")

    monkeypatch.setattr(ollama_client, "embed", fake_embed)

    client = TestClient(main.app)
    r = client.post(
        "/api/item",
        data={"kind": "message", "sender": "Dagger", "text": "I want to die"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["crisis"] is True
    assert "14416" in body["message"]
    assert called["n"] == 0


def test_save_anyway_keeps_the_note_without_calling_embed(monkeypatch, tmp_path):
    from app import db, ollama_client
    from app.routes import items as items_module

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(items_module, "MEDIA_DIR", tmp_path / "media")

    called = {"n": 0}

    async def fake_embed(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("embed must not run for a save-anyway note")

    monkeypatch.setattr(ollama_client, "embed", fake_embed)

    client = TestClient(main.app)
    r = client.post(
        "/api/item",
        data={
            "kind": "message",
            "sender": "Dagger",
            "text": "I want to die",
            "save_anyway": "true",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["saved"] is True
    assert body["crisis"] is True
    assert called["n"] == 0, "no model may be called when safety trips"

    with db.connect(tmp_path / "t.db") as conn:
        rows = db.list_items(conn, "message")
    assert len(rows) == 1
    assert rows[0]["text"] == "I want to die"
    assert rows[0]["emb"] is None


def test_admin_delete_ok_with_passcode(monkeypatch, tmp_path):
    from app import db
    from app.routes import items as items_module

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(items_module, "MEDIA_DIR", tmp_path / "media")
    _set_passcode(monkeypatch, "s3cret")

    with db.connect(tmp_path / "t.db") as conn:
        db.insert_item(conn, item_id="m1", kind="message", sender="A", text="bye", created=1.0)

    client = TestClient(main.app)
    r = client.delete("/api/item/m1", headers={"X-Admin-Passcode": "s3cret"})
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    with db.connect(tmp_path / "t.db") as conn:
        assert db.list_items(conn, "message") == []
