"""Tests for the Ollama client, focused on the model override."""

from __future__ import annotations

from app import ollama_client
from app.config import settings


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"message": {"content": "ok"}}


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def post(self, url, json=None):
        _FakeClient.last = {"url": url, "json": json}
        return _FakeResponse()


async def test_chat_defaults_to_the_configured_model(monkeypatch):
    monkeypatch.setattr(ollama_client.httpx, "AsyncClient", _FakeClient)
    await ollama_client.chat(system="s", user="u")
    assert _FakeClient.last["json"]["model"] == settings.chat_model


async def test_chat_model_override_is_used(monkeypatch):
    monkeypatch.setattr(ollama_client.httpx, "AsyncClient", _FakeClient)
    await ollama_client.chat(system="s", user="u", model="other:7b")
    assert _FakeClient.last["json"]["model"] == "other:7b"
    assert _FakeClient.last["url"].startswith(settings.ollama_url)
