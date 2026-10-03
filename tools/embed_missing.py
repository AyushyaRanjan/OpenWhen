"""Backfill vectors for wins that were logged while Ollama was down.

A win the friend logs is embedded on the spot so it can be matched later. If
Ollama happened to be off, the words are still saved but without a vector, and
retrieval skips them. Run this once when Ollama is back to fill those in.

Only kind 'win' rows are touched. Messages are deliberately left alone: a
save-anyway note is stored vectorless on purpose (its safety check tripped), and
embedding it later would hand it to the model, which must never happen.

It only ever talks to the local Ollama server named in config, logs counts and
never the text. See AGENTS.md.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
# Running this file directly puts tools/ first on sys.path, so add the repo root
# before importing the app package.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import db  # noqa: E402
from app import ollama_client  # noqa: E402
from app.ollama_client import OllamaUnavailable  # noqa: E402


def unembedded_wins(db_path: str | None = None) -> list[tuple[str, str]]:
    """(id, text) for wins with no vector. Callers must not log the text."""
    with db.connect(db_path or db.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, text FROM items WHERE kind = 'win' AND emb IS NULL"
        ).fetchall()
    return [(row["id"], row["text"]) for row in rows]


async def backfill(db_path: str | None = None) -> int:
    """Embed every vectorless win. Returns how many were filled in.

    Stops early and returns what it managed if Ollama goes away mid-run; the
    remaining wins are picked up on the next run.
    """
    pending = unembedded_wins(db_path)
    if not pending:
        return 0

    done = 0
    with db.connect(db_path or db.DB_PATH) as conn:
        for item_id, text in pending:
            try:
                emb = await ollama_client.embed(text)
            except OllamaUnavailable:
                break
            db.update_embedding(conn, item_id, emb)
            done += 1
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default=None,
        help="database file (defaults to the app's comfort.db)",
    )
    args = parser.parse_args()

    try:
        filled = asyncio.run(backfill(args.db))
    except OllamaUnavailable:
        print("Ollama isn't running. Start it and try again; nothing was changed.")
        return 1

    print(f"Embedded {filled} win(s). Run again any time; it only adds what's missing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
