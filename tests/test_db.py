"""Storage tests. Each one runs against a throwaway file in tmp_path, so the
real comfort.db is never touched."""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from app import db


@pytest.fixture()
def conn(tmp_path):
    connection = db.connect(tmp_path / "test-comfort.db")
    yield connection
    connection.close()


def test_insert_then_list_gives_back_what_went_in(conn):
    db.insert_item(
        conn,
        item_id="m1",
        kind="message",
        sender="Dagger",
        text="Thinking of you.",
        created=1000.0,
    )

    rows = db.list_items(conn, "message")

    assert len(rows) == 1
    assert rows[0]["id"] == "m1"
    assert rows[0]["sender"] == "Dagger"
    assert rows[0]["text"] == "Thinking of you."
    assert rows[0]["created"] == 1000.0


def test_list_is_newest_first_and_filtered_by_kind(conn):
    # Explicit timestamps, not the clock: two inserts in the same fraction of
    # a second would otherwise land in an arbitrary order.
    db.insert_item(conn, item_id="m1", kind="message", sender="A", text="one", created=1000.0)
    db.insert_item(conn, item_id="m2", kind="message", sender="B", text="two", created=3000.0)
    db.insert_item(conn, item_id="m3", kind="message", sender="C", text="three", created=2000.0)
    db.insert_item(conn, item_id="w1", kind="win", sender="Friend", text="got up", created=4000.0)

    messages = db.list_items(conn, "message")

    assert [row["id"] for row in messages] == ["m2", "m3", "m1"]
    assert [row["id"] for row in db.list_items(conn, "win")] == ["w1"]


def test_delete_item_says_whether_it_found_anything(conn):
    db.insert_item(conn, item_id="m1", kind="message", sender="A", text="bye", created=1000.0)

    assert db.delete_item(conn, "m1") is True
    assert db.delete_item(conn, "m1") is False
    assert db.list_items(conn, "message") == []


def test_embeddings_come_back_as_vectors_and_unembedded_rows_are_skipped(conn):
    vector = np.array([0.1, 0.2, 0.3], dtype=np.float64)
    db.insert_item(
        conn, item_id="m1", kind="message", sender="A", text="with a vector",
        emb=vector, created=1000.0,
    )
    db.insert_item(conn, item_id="m2", kind="message", sender="A", text="no vector", created=2000.0)

    found = db.get_all_with_embeddings(conn, "message")

    # m2 is left out: an item with no vector can't be scored, and a zero vector
    # in its place would match everything.
    assert [row["id"] for row, _ in found] == ["m1"]
    np.testing.assert_allclose(found[0][1], vector.astype(np.float32))


def test_kind_rejects_anything_but_message_or_win(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.insert_item(conn, item_id="x1", kind="note", sender="A", text="typo", created=1000.0)
