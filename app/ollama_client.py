"""Talking to the local Ollama server.

Both the URL and both model names come from config; nothing here may build a
URL string or name a model in code. An Ollama server that isn't running is an
expected state: callers get a clear, custom exception to handle gracefully.
See AGENTS.md.
"""

from __future__ import annotations

from typing import Any

import httpx
import numpy as np

from app.config import settings


class OllamaUnavailable(Exception):
    """Raised when the local Ollama server cannot be reached or responds badly."""

    def __init__(self, message: str = "Ollama server is not available right now.") -> None:
        super().__init__(message)


async def embed(text: str) -> np.ndarray:
    """Return a float32 embedding vector for the given text."""
    try:
        payload = {
            "model": settings.embed_model,
            "input": text,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                settings.ollama_url.rstrip("/") + "/api/embed", json=payload
            )
            r.raise_for_status()
            data = r.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, TypeError) as exc:
        raise OllamaUnavailable(f"Could not get embedding from Ollama: {exc}") from exc

    # Ollama returns {"embeddings": [[...]]} or {"embedding": [...]} depending on version
    vectors: list[list[float]] = []
    if isinstance(data, dict):
        if isinstance(data.get("embeddings"), list) and data["embeddings"]:
            first = data["embeddings"][0]
            if isinstance(first, list):
                vectors = [first]
        if not vectors and isinstance(data.get("embedding"), list):
            vectors = [data["embedding"]]

    if not vectors:
        raise OllamaUnavailable("Ollama returned no embeddings.")

    vec = np.array(vectors[0], dtype=np.float32)
    return vec


async def chat(
    system: str | None = None,
    user: str | None = None,
    max_tokens: int | None = None,
    messages: list[dict[str, str]] | None = None,
    temperature: float = 0.7,
    keep_alive: str | None = None,
    model: str | None = None,
) -> str:
    """Chat with a model, returning content as a string.

    Accepts either (system, user, max_tokens) or a raw messages list for
    compatibility with existing callers. `model` is only used by the offline
    comparison tool; the app always leaves it None so config decides.
    """
    try:
        if messages is None:
            msg_list: list[dict[str, str]] = []
            if system:
                msg_list.append({"role": "system", "content": system})
            if user is not None:
                msg_list.append({"role": "user", "content": user})
            else:
                msg_list.append({"role": "user", "content": ""})
        else:
            msg_list = list(messages)

        payload: dict[str, Any] = {
            "model": model or settings.chat_model,
            "messages": msg_list,
            "stream": False,
            "temperature": temperature,
        }
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        else:
            payload["keep_alive"] = settings.keep_alive
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                settings.ollama_url.rstrip("/") + "/api/chat", json=payload
            )
            r.raise_for_status()
            data = r.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, TypeError) as exc:
        raise OllamaUnavailable(f"Could not chat with Ollama: {exc}") from exc

    content = ""
    if isinstance(data, dict):
        msg = data.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            content = msg["content"]
        elif isinstance(data.get("content"), str):
            content = data["content"]
    return content

