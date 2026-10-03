"""The FastAPI app. Routers get added here as they are built."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR
from app.routes import feel, items, meta

log = logging.getLogger(__name__)

app = FastAPI(title="Open When...")


@app.get("/api/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


app.include_router(items.router)
app.include_router(feel.router)
app.include_router(meta.router)


# Any API router goes above this line, not below.

_MEDIA_DIR = BASE_DIR / "media"
if _MEDIA_DIR.is_dir():
    app.mount("/media", StaticFiles(directory=_MEDIA_DIR), name="media")

_STATIC_DIR = BASE_DIR / "static"
if _STATIC_DIR.is_dir():
    # Mounted last on purpose. This catch-all sits at "/", so anything
    # registered after it would be unreachable. All /api routes must stay above.
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    # 127.0.0.1 hardcoded, never a variable: this is a single-user app on one
    # person's laptop and must not be reachable from the network.
    uvicorn.run(app, host="127.0.0.1", port=8000)
