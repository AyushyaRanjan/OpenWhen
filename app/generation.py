"""Shared generation logic for the lead-in and the tiny step.

Kept out of the route so the app and the model-comparison tool run the exact
same code path. The system prompts are read from prompts/; see app/prompts.py.
Callers decide the fallback text, so a local Ollama that is not running stays
an expected, graceful state. See AGENTS.md.
"""

from __future__ import annotations

from typing import Any

from app import ollama_client, prompts, retrieval

DEFAULT_LEAD = "Here's something from someone who cares about you."
DEFAULT_STEP = "Just one tiny thing you could try right now."

LEAD_MAX_TOKENS = 120
STEP_MAX_TOKENS = 60


def build_lead_context(
    messages: list[dict[str, Any]], wins: list[dict[str, Any]]
) -> str:
    """Turn retrieved items into the plain text the model is allowed to use.

    Only senders and texts go in, so the model has nothing else it could have
    seen. It still must not be trusted to add facts; the prompt says so too.
    """
    parts: list[str] = []
    if messages:
        parts.append("Messages from loved ones:")
        for m in messages:
            parts.append(f"- {m.get('sender')}: {m.get('text')}")
    if wins:
        parts.append("Wins:")
        for w in wins:
            parts.append(f"- {w.get('text')}")
    return "\n".join(parts) if parts else "No specific items found."


async def gather_items(
    mood: str,
    text: str,
    recently_shown_ids: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Embed the feeling and pull matching messages and wins from the DB.

    Wins are looked up on a mood tap as well as typed text, and the fallback in
    retrieval still returns one even when Ollama's embedding model is down, so
    the friend's own wins are not stranded. This is read only. An embedding or
    retrieval failure degrades to an empty list, never an error.
    """
    query = f"{mood}. {text}" if mood or text else "feeling"

    qemb = None
    try:
        qemb = await ollama_client.embed(query)
    except Exception:
        qemb = None

    messages_list: list[dict[str, Any]] = []
    wins_list: list[dict[str, Any]] = []

    try:
        messages_list = retrieval.top_k(
            "message", qemb, k=2, recently_shown_ids=recently_shown_ids, fallback_k=2
        )
    except Exception:
        messages_list = []

    try:
        # One win at most, and only one they have not just seen, so the same
        # small victory does not become wallpaper.
        wins_list = retrieval.top_k(
            "win", qemb, k=2, recently_shown_ids=recently_shown_ids, fallback_k=1
        )
    except Exception:
        wins_list = []

    return {"messages": messages_list, "wins": wins_list}


async def generate_lead(
    messages: list[dict[str, Any]],
    wins: list[dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
) -> str:
    """Produce the warm 1-2 sentence lead-in for the given items.

    Raises whatever ollama_client raises (e.g. OllamaUnavailable); the caller
    chooses the fallback.
    """
    resp = await ollama_client.chat(
        system=prompts.load("lead_in"),
        user=build_lead_context(messages, wins),
        max_tokens=LEAD_MAX_TOKENS,
        model=model,
        temperature=temperature,
    )
    return (resp or "").strip()


async def generate_step(
    challenge: str,
    *,
    model: str | None = None,
    temperature: float = 0.7,
) -> str:
    """Produce one tiny, kind step for the given challenge."""
    resp = await ollama_client.chat(
        system=prompts.load("tiny_step"),
        user=challenge or "feeling stuck",
        max_tokens=STEP_MAX_TOKENS,
        model=model,
        temperature=temperature,
    )
    return (resp or "").strip()
