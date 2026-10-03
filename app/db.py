"""SQLite storage for messages from loved ones and the friend's own wins.

One table, standard library sqlite3, no ORM. Every helper takes a connection so
tests can point at a temporary file instead of the real comfort.db.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import numpy as np

from app.config import BASE_DIR

DB_PATH = BASE_DIR / "comfort.db"

# 'kind' is constrained in the schema so a typo can't quietly create a third
# kind that list_items would never return.
SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id      TEXT PRIMARY KEY,
    kind    TEXT NOT NULL CHECK (kind IN ('message', 'win')),
    sender  TEXT NOT NULL,
    text    TEXT NOT NULL,
    audio   TEXT,
    mood    TEXT,
    emb     BLOB,
    created REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_kind_created ON items (kind, created DESC);
"""


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    # Resolve DB_PATH at call time, not as a default argument. A default would
    # be bound once at import, so tests that point DB_PATH at a tmp file would
    # silently keep writing to the real comfort.db.
    target = DB_PATH if db_path is None else db_path
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _encode(emb: np.ndarray | None) -> bytes | None:
    if emb is None:
        return None
    # float32 everywhere so a stored vector and a fresh one are always
    # byte-comparable, whatever dtype numpy handed us.
    return np.asarray(emb, dtype=np.float32).tobytes()


def _decode(blob: bytes | None) -> np.ndarray | None:
    if not blob:
        return None
    return np.frombuffer(blob, dtype=np.float32)


def insert_item(
    conn: sqlite3.Connection,
    *,
    item_id: str,
    kind: str,
    sender: str,
    text: str,
    audio: str | None = None,
    mood: str | None = None,
    emb: np.ndarray | None = None,
    created: float | None = None,
) -> None:
    """Store one message or win. `created` defaults to now, in epoch seconds."""
    conn.execute(
        """
        INSERT INTO items (id, kind, sender, text, audio, mood, emb, created)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            kind,
            sender,
            text,
            audio,
            mood,
            _encode(emb),
            time.time() if created is None else float(created),
        ),
    )
    # Committed here rather than by the caller: one user, one app, and a lost
    # note someone recorded by hand is not worth a transaction abstraction.
    conn.commit()


def list_items(conn: sqlite3.Connection, kind: str) -> list[sqlite3.Row]:
    """Newest first. Rows carry the text, so callers must not log them."""
    return conn.execute(
        "SELECT * FROM items WHERE kind = ? ORDER BY created DESC",
        (kind,),
    ).fetchall()


def delete_item(conn: sqlite3.Connection, item_id: str) -> bool:
    """Remove one item. Returns whether it was actually there."""
    cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    return cursor.rowcount > 0


def get_all_with_embeddings(
    conn: sqlite3.Connection, kind: str
) -> list[tuple[sqlite3.Row, np.ndarray]]:
    """Items that actually have a vector, newest first.

    Unembedded items are skipped: they cannot be scored, and standing in a
    zero vector for them would let them match everything.
    """
    rows = conn.execute(
        """
        SELECT * FROM items
        WHERE kind = ? AND emb IS NOT NULL
        ORDER BY created DESC
        """,
        (kind,),
    ).fetchall()

    found: list[tuple[sqlite3.Row, np.ndarray]] = []
    for row in rows:
        vector = _decode(row["emb"])
        if vector is None or vector.size == 0:
            continue
        found.append((row, vector))
    return found
