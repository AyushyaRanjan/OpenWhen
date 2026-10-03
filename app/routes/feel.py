"""Feel, step, win routes."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from app import db, generation, safety

router = APIRouter()


@router.get("/api/recent")
async def recent(k: int = 5) -> dict[str, list[dict[str, Any]]]:
    """A few recent notes from loved ones, no model, no matching.

    The friend's phone calls this once while it is online so the resting screen
    has something real to show if the server later disappears. It returns only
    kind 'message' (never the friend's own wins) and never an embedding.
    """
    k = max(1, min(int(k), 10))
    with db.connect() as conn:
        rows = db.list_items(conn, "message")[:k]
    out: list[dict[str, Any]] = []
    for row in rows:
        item = {key: row[key] for key in row.keys()}
        item.pop("emb", None)
        out.append(item)
    return {"messages": out}


@router.post("/api/feel")
async def feel(payload: dict[str, Any]):
    mood = str(payload.get("mood", ""))
    text = str(payload.get("text", ""))
    recently_shown_ids = payload.get("recently_shown_ids") or []

    # Safety first: if this trips, no model is touched at all.
    if text and await safety.acheck(text):
        return {**safety.crisis_response(), "crisis": True}

    items = await generation.gather_items(mood, text, recently_shown_ids)
    messages_list = items["messages"]
    wins_list = items["wins"]

    lead = generation.DEFAULT_LEAD
    try:
        produced = await generation.generate_lead(messages_list, wins_list)
        if produced:
            lead = produced
    except Exception:
        # Ollama being down is expected; fall back to the human-written line.
        lead = generation.DEFAULT_LEAD

    return {
        "crisis": False,
        "lead": lead,
        "messages": messages_list,
        "wins": wins_list,
    }


@router.post("/api/step")
async def step(payload: dict[str, Any]):
    challenge = str(payload.get("challenge", ""))
    if challenge and await safety.acheck(challenge):
        return {**safety.crisis_response(), "crisis": True}

    step_text = generation.DEFAULT_STEP
    try:
        produced = await generation.generate_step(challenge)
        if produced:
            step_text = produced
    except Exception:
        step_text = generation.DEFAULT_STEP

    return {"crisis": False, "step": step_text}


@router.post("/api/win")
async def win(payload: dict[str, Any]):
    text = str(payload.get("text", ""))
    if text and await safety.acheck(text):
        return {**safety.crisis_response(), "crisis": True}

    with db.connect() as conn:
        db.insert_item(
            conn,
            item_id=str(uuid.uuid4()),
            kind="win",
            sender="me",
            text=text,
            audio=None,
            mood=None,
            emb=None,
        )

    return {"ok": True}
