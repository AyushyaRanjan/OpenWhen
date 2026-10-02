"""Talking to the local Ollama server.

Both the URL and both model names come from config; nothing here may build a
URL string or name a model in code. An Ollama server that isn't running is an
expected state, so callers get a clear flag rather than an exception. See
AGENTS.md.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


async def chat(
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    keep_alive: str | None = None,
) -> dict[str, Any]:
    """A minimal chat call to the configured Ollama model.

    Returns {"content": str, "model": str} on success. On failure (server down,
    timeout, bad response) this raises — the caller decides how to degrade.
    """
    payload = {
        "model": settings.chat_model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    else:
        payload["keep_alive"] = settings.keep_alive

    # Only read the URL from config — never construct extra paths here.
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(settings.ollama_url.rstrip("/") + "/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()

    content = data.get("message", {}).get("content", "") if isinstance(data, dict) else ""
    return {
        "content": content if isinstance(content, str) else "",
        "model": data.get("model") if isinstance(data, dict) else settings.chat_model,
    }
