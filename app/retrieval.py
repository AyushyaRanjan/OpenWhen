"""Picking the right messages and wins for a feeling.

Cosine similarity over the vectors in db.get_all_with_embeddings, using numpy.
Scores below config's min_match_score are not a match. If nothing matches for
kind 'message', the fallback returns the 2 most recent messages from loved ones.
See AGENTS.md.
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
    query_embedding: np.ndarray,
    k: int,
    min_score: float | None = None,
    recently_shown_ids: list[str] | None = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Return top-k similar items of given kind.

    If kind == 'message' and nothing passes the threshold, return the 2 most
    recent messages as fallback (fallback=True). Recently-shown IDs are
    deprioritised (their score is nudged down slightly) to avoid repeats.
    """
    min_s = float(min_score) if min_score is not None else float(settings.min_match_score)
    shown = set(recently_shown_ids or [])

    q = np.asarray(query_embedding, dtype=np.float32).ravel()
    candidates: list[tuple[float, dict[str, Any]]] = []
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

    # Fallback: if no matches for messages, return the 2 most recent messages
    if len(results) == 0 and kind == "message":
        with db.connect(db_path or db.DB_PATH) as conn:
            rows = db.list_items(conn, "message")[:2]
        for r in rows:
            rd = _row_to_dict(r)
            rd["score"] = 0.0
            rd["fallback"] = True
            results.append(rd)
            if len(results) >= k:
                break

    return results[:k]
