"""Picking the right messages and wins for a feeling.

Cosine similarity over the vectors in db.get_all_with_embeddings, using numpy.
Scores below config's min_match_score are not a match. If nothing matches, the
fallback returns recent unshown items instead: 2 messages from loved ones, or 1
of the friend's own wins. See AGENTS.md.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app import db
from app.config import settings


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    # Normalise in float32 for stable, simple cosine
    a = np.asarray(a, dtype=np.float32).ravel()
    b = np.asarray(b, dtype=np.float32).ravel()
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12
    return float((a @ b) / denom)


def _row_to_dict(row: Any) -> dict[str, Any]:
    # sqlite3.Row supports mapping. The vector is raw bytes and is never part of
    # an API response, so drop it here or JSON encoding blows up.
    out: dict[str, Any] = {}
    for k in row.keys():
        if k == "emb":
            continue
        out[k] = row[k]
    return out


def top_k(
    kind: str,
    query_embedding: np.ndarray | None,
    k: int,
    min_score: float | None = None,
    recently_shown_ids: list[str] | None = None,
    db_path: str | None = None,
    fallback_k: int | None = None,
) -> list[dict[str, Any]]:
    """Return top-k similar items of given kind.

    If nothing passes the threshold, `fallback_k` real items are returned
    instead (fallback=True), so a quiet match never leaves the screen empty:
    2 most-recent messages by default, and the caller asks for 1 win. Passing
    nothing uses the kind's default (2 for messages, 0 otherwise).

    `query_embedding` may be None when the embedding model is unreachable. Then
    nothing can be scored and the fallback (if any) still runs, so the friend's
    own wins come back even while Ollama is down.

    Recently-shown IDs are deprioritised (their score is nudged down slightly)
    to avoid repeats, and are skipped when choosing fallback items.
    """
    min_s = float(min_score) if min_score is not None else float(settings.min_match_score)
    if fallback_k is None:
        fallback_k = 2 if kind == "message" else 0
    shown = set(recently_shown_ids or [])

    candidates: list[tuple[float, dict[str, Any]]] = []
    if query_embedding is not None:
        q = np.asarray(query_embedding, dtype=np.float32).ravel()
        with db.connect(db_path or db.DB_PATH) as conn:
            for row, emb in db.get_all_with_embeddings(conn, kind):
                rowd = _row_to_dict(row)
                e = np.asarray(emb, dtype=np.float32).ravel()
                if e.size != q.size:
                    # Written by a different embedding model. Comparing them is
                    # meaningless, and one stale row must not break every lookup.
                    continue
                score = _cosine(q, e)
                if rowd.get("id") in shown:
                    # Deprioritise repeats without hiding them entirely
                    score = score - 0.05
                candidates.append((score, rowd))

    candidates.sort(key=lambda x: x[0], reverse=True)

    results: list[dict[str, Any]] = []
    for score, rowd in candidates:
        if score < min_s:
            continue
        rd = dict(rowd)
        rd["score"] = float(score)
        rd["fallback"] = False
        results.append(rd)
        if len(results) >= k:
            break

    # Fallback: nothing matched, so show something real and unshown instead.
    if len(results) == 0 and fallback_k > 0:
        with db.connect(db_path or db.DB_PATH) as conn:
            rows = db.list_items(conn, kind)
        fresh = [r for r in rows if r["id"] not in shown]
        # If the friend has already seen everything, fall back to the newest
        # rather than showing nothing at all.
        for r in (fresh or rows)[:fallback_k]:
            rd = _row_to_dict(r)
            rd["score"] = 0.0
            rd["fallback"] = True
            results.append(rd)

    return results[:k]
