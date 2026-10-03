"""Retrieval tests: cosine ranking, min_score filtering, fallback, and
recently-shown deprioritisation.
"""

from __future__ import annotations

import numpy as np

from app import db, retrieval


def test_cosine_ranking(tmp_path, monkeypatch):
    # Point DB to temp file
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    with db.connect(db_path) as conn:
        # Items with known directions
        db.insert_item(
            conn, item_id="m1", kind="message", sender="A", text="hello world",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=1000.0,
        )
        db.insert_item(
            conn, item_id="m2", kind="message", sender="B", text="hi there",
            emb=np.array([0.0, 1.0], dtype=np.float32), created=2000.0,
        )
        db.insert_item(
            conn, item_id="m3", kind="message", sender="C", text="hello again",
            emb=np.array([0.9, 0.1], dtype=np.float32), created=3000.0,
        )

    query = np.array([1.0, 0.0], dtype=np.float32)
    results = retrieval.top_k("message", query, k=3, min_score=0.0)
    ids = [r["id"] for r in results]
    assert ids == ["m1", "m3", "m2"]
    # scores should be present and in descending order
    scores = [r["score"] for r in results]
    assert scores[0] >= scores[1] >= scores[2]


def test_min_score_filters_out_weak_matches(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    with db.connect(db_path) as conn:
        db.insert_item(
            conn, item_id="m1", kind="message", sender="A", text="x",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=1000.0,
        )
        db.insert_item(
            conn, item_id="m2", kind="message", sender="B", text="y",
            emb=np.array([0.0, 1.0], dtype=np.float32), created=2000.0,
        )

    query = np.array([1.0, 0.0], dtype=np.float32)
    results = retrieval.top_k("message", query, k=5, min_score=0.95)
    assert [r["id"] for r in results] == ["m1"]
    assert all(r["fallback"] is False for r in results)


def test_fallback_returns_two_most_recent_when_nothing_matches(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    with db.connect(db_path) as conn:
        db.insert_item(
            conn, item_id="m1", kind="message", sender="A", text="old",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=1000.0,
        )
        db.insert_item(
            conn, item_id="m2", kind="message", sender="B", text="newer",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=2000.0,
        )
        db.insert_item(
            conn, item_id="m3", kind="message", sender="C", text="newest",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=3000.0,
        )

    # Query orthogonal -> all scores low
    query = np.array([0.0, 1.0], dtype=np.float32)
    results = retrieval.top_k("message", query, k=5, min_score=0.9)
    # fallback: 2 most recent (m3, m2)
    assert [r["id"] for r in results] == ["m3", "m2"]
    assert all(r["fallback"] is True for r in results)
    assert all(r["score"] == 0.0 for r in results)


def test_recently_shown_deprioritised(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    with db.connect(db_path) as conn:
        db.insert_item(
            conn, item_id="m1", kind="message", sender="A", text="a",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=1000.0,
        )
        db.insert_item(
            conn, item_id="m2", kind="message", sender="B", text="b",
            emb=np.array([0.99, 0.01], dtype=np.float32), created=2000.0,
        )

    query = np.array([1.0, 0.0], dtype=np.float32)
    # Without recently shown, m1 should be first
    results1 = retrieval.top_k("message", query, k=2, min_score=0.0)
    assert results1[0]["id"] == "m1"

    # If m1 was recently shown, it gets nudged down; m2 moves up
    results2 = retrieval.top_k("message", query, k=2, min_score=0.0, recently_shown_ids=["m1"])
    assert results2[0]["id"] == "m2"
    assert results2[1]["id"] == "m1"


def test_mismatched_embedding_dimension_is_skipped(tmp_path, monkeypatch):
    # A row written by a different embedding model must not crash retrieval;
    # it is simply not comparable and gets skipped.
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    with db.connect(db_path) as conn:
        db.insert_item(
            conn, item_id="stale", kind="message", sender="A", text="old model",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=1000.0,
        )
        db.insert_item(
            conn, item_id="good", kind="message", sender="B", text="new model",
            emb=np.array([1.0, 0.0, 0.0], dtype=np.float32), created=2000.0,
        )

    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    results = retrieval.top_k("message", query, k=5, min_score=0.9)
    assert [r["id"] for r in results] == ["good"]


def test_results_never_contain_the_raw_embedding(tmp_path, monkeypatch):
    # The vector is bytes; leaking it into a result breaks JSON responses.
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    with db.connect(db_path) as conn:
        db.insert_item(
            conn, item_id="m1", kind="message", sender="A", text="hello",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=1000.0,
        )

    query = np.array([1.0, 0.0], dtype=np.float32)
    for r in retrieval.top_k("message", query, k=5, min_score=0.0):
        assert "emb" not in r


def test_win_fallback_returns_recent_unshown_win(tmp_path, monkeypatch):
    # A win with no close match must still come back, and never one the friend
    # just saw if a fresher one is available.
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)

    with db.connect(db_path) as conn:
        db.insert_item(
            conn, item_id="w1", kind="win", sender="me", text="older",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=1000.0,
        )
        db.insert_item(
            conn, item_id="w2", kind="win", sender="me", text="newer",
            emb=np.array([1.0, 0.0], dtype=np.float32), created=2000.0,
        )

    query = np.array([0.0, 1.0], dtype=np.float32)  # orthogonal: nothing matches
    results = retrieval.top_k("win", query, k=2, min_score=0.9, fallback_k=1)
    assert [r["id"] for r in results] == ["w2"]
    assert results[0]["fallback"] is True

    # w2 already shown -> fall back to the next unshown win.
    results = retrieval.top_k(
        "win", query, k=2, min_score=0.9, fallback_k=1, recently_shown_ids=["w2"]
    )
    assert [r["id"] for r in results] == ["w1"]


def test_top_k_handles_a_none_query_by_falling_back(tmp_path, monkeypatch):
    # Ollama's embedding model can be down; retrieval must not crash and should
    # still offer a real win from the fallback.
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    with db.connect(db_path) as conn:
        db.insert_item(conn, item_id="w1", kind="win", sender="me", text="a win", created=1000.0)

    results = retrieval.top_k("win", None, k=2, fallback_k=1)
    assert [r["id"] for r in results] == ["w1"]
    assert results[0]["fallback"] is True
