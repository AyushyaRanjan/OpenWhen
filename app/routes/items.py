"""Item routes: create, list, delete messages/wins with optional audio."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app import db, ollama_client, safety
from app.auth import require_admin
from app.config import BASE_DIR

router = APIRouter()

MEDIA_DIR = BASE_DIR / "media"
ALLOWED_EXT = {".webm", ".mp4", ".m4a", ".ogg", ".mp3", ".wav"}
MAX_AUDIO_BYTES = 15 * 1024 * 1024


def _safe_ext(name: str | None) -> str | None:
    if not name:
        return None
    ext = os.path.splitext(name.lower())[1]
    return ext if ext in ALLOWED_EXT else None


@router.post("/api/item")
async def create_item(
    kind: str = Form(...),
    sender: str = Form(...),
    text: str = Form(...),
    mood: str = Form(""),
    save_anyway: bool = Form(False),
    audio: Optional[UploadFile] = File(None),
):
    # Basic validation
    if kind not in ("message", "win"):
        raise HTTPException(status_code=400, detail="kind must be 'message' or 'win'")

    # Safety runs BEFORE the embedding call below. If it trips, no model is
    # touched and no audio is written. A contributor who is sure their words
    # are meant as support may pass save_anyway=true: the note is then kept
    # without a vector, so still no model is called. See AGENTS.md.
    tripped = bool(text) and await safety.acheck(text)
    if tripped and not save_anyway:
        return {**safety.crisis_response(), "crisis": True}

    audio_path: str | None = None
    if audio is not None:
        if audio.size and audio.size > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=400, detail="audio file too large (max 15 MB)")
        ext = _safe_ext(audio.filename)
        if ext is None:
            raise HTTPException(status_code=400, detail="unsupported audio extension")
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4()}{ext}"
        dest = MEDIA_DIR / filename
        content = await audio.read()
        if len(content) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=400, detail="audio file too large (max 15 MB)")
        with dest.open("wb") as f:
            f.write(content)
        audio_path = filename

    emb = None
    if not tripped:
        # Build query for embedding: "mood. text" (simple, safe)
        query = f"{mood}. {text}" if mood else text
        try:
            emb = await ollama_client.embed(query)
        except Exception as exc:
            # Ollama unavailable is an expected state; degrade with clear message
            raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc

    item_id = str(uuid.uuid4())
    with db.connect() as conn:
        db.insert_item(
            conn,
            item_id=item_id,
            kind=kind,
            sender=sender,
            text=text,
            audio=audio_path,
            mood=mood or None,
            emb=emb,
        )

    if tripped:
        # Kept without a vector. Lets the form say plainly that it was saved.
        return {"id": item_id, "audio": audio_path, "crisis": True, "saved": True}
    return {"id": item_id, "audio": audio_path}


@router.get("/api/items")
async def list_items(kind: str, _: None = Depends(require_admin)):
    if kind not in ("message", "win"):
        raise HTTPException(status_code=400, detail="kind must be 'message' or 'win'")
    with db.connect() as conn:
        rows = db.list_items(conn, kind)
    # Return serialisable data without blob
    out = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        d.pop("emb", None)
        out.append(d)
    return out


@router.delete("/api/item/{item_id}")
async def delete_item(item_id: str, _: None = Depends(require_admin)):
    audio_path: str | None = None
    # Find audio to delete file
    with db.connect() as conn:
        rows = conn.execute("SELECT audio FROM items WHERE id = ?", (item_id,)).fetchall()
        if rows:
            audio_path = rows[0]["audio"] if rows[0]["audio"] else None
        deleted = db.delete_item(conn, item_id)

    if not deleted and not rows:
        raise HTTPException(status_code=404, detail="not found")

    if audio_path:
        try:
            (MEDIA_DIR / audio_path).unlink(missing_ok=True)
        except Exception:
            pass

    return {"deleted": True}
