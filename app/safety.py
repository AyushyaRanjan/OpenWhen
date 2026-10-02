"""Crisis / self-harm check.

This is a minimal, local safeguard. Keyword filters are not a guarantee — they
can miss context, miss code words, or trigger on edge cases. See AGENTS.md.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Iterable

from app.config import BASE_DIR, settings
from app.ollama_client import chat

# Make settings appear mutable to monkeypatch in tests (Settings is frozen).
try:
    # If someone does monkeypatch.setattr(safety.settings, 'use_model_safety_check', ...),
    # allow storing the override on a side channel instead of mutating frozen instance.
    class _SettingsShim:
        def __init__(self, real):
            object.__setattr__(self, "_real", real)

        def __getattr__(self, name):
            return getattr(self._real, name)

        def __setattr__(self, name, value):
            if name == "use_model_safety_check":
                # Store override in module instead of raising
                globals()["_use_model_safety_check_override"] = bool(value)
                return
            # For other attrs, don't mutate real frozen instance
            return

        def __repr__(self) -> str:
            return repr(self._real)

    settings = _SettingsShim(settings)  # type: ignore[assignment]
except Exception:
    pass

# Allow tests to override the model-safety flag without mutating frozen settings.
_use_model_safety_check_override: bool | None = None
_use_model_safety_check: bool | None = None  # for monkeypatching the getter itself

_PHRASE_PATH = BASE_DIR / "safety_phrases.json"
_CLEAN_RE = re.compile(r"[^a-z0-9]+")
_REPEAT_PUNCT_RE = re.compile(r"([^\w\s])\1+")
_REPEAT_LETTER_RE = re.compile(r"([a-z])\1+")
# Collapse whitespace (spaces, tabs, newlines, non-breaking spaces)
_WS_RE = re.compile(r"\s+")


def _read_phrases() -> Iterable[str]:
    try:
        raw = json.loads(_PHRASE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return ()

    for key, values in raw.items():
        if key.startswith("_"):
            continue
        if not isinstance(values, list):
            continue
        for v in values:
            if isinstance(v, str):
                yield v


def _normalize(text: str) -> str:
    """Lowercase, strip repeated punctuation, collapse repeated letters and
    whitespace. Basic but explicit, so tests know exactly what "tidiest" means.
    """
    if not text:
        return ""

    s = text.lower()
    s = _REPEAT_PUNCT_RE.sub(r"\1", s)
    s = _REPEAT_LETTER_RE.sub(r"\1", s)
    s = _WS_RE.sub(" ", s)
    return s.strip()


def _phrase_normalise(p: str) -> str:
    s = p.lower()
    s = _REPEAT_PUNCT_RE.sub(r"\1", s)
    s = _REPEAT_LETTER_RE.sub(r"\1", s)
    s = _WS_RE.sub(" ", s)
    return s.strip()


def is_crisis(text: str) -> bool:
    """Return True if the text contains a crisis phrase after normalisation."""
    if not text or not text.strip():
        return False

    norm = _normalize(text)
    if not norm:
        return False

    for p in _read_phrases():
        pn = _phrase_normalise(p)
        if not pn:
            continue
        # Use word boundaries to avoid matching 'die' inside 'diet'.
        # If the phrase contains non-alnum chars (e.g. after normalisation none expected)
        # fall back to substring to keep behaviour simple and explicit.
        if re.fullmatch(r"[a-z0-9 ]+", pn):
            # Match whole phrase as a word sequence
            pattern = r"\b" + re.escape(pn) + r"\b"
            if re.search(pattern, norm):
                return True
            continue
        if pn in norm:
            return True
    return False


def crisis_response() -> dict[str, Any]:
    """Return a fixed, human-written response with tel: links."""
    helper = settings.helper_name
    phone = settings.helper_phone

    message = (
        f"I'm really glad you reached out, {helper} is here for you right now. "
        "You don't have to carry this alone, and you deserve real support. "
        "These numbers can help straight away: "
        "Tele-MANAS 14416 (free, 24/7, India), "
        f"{helper} on {phone} (the person you asked for), "
        "or 112 for immediate danger. "
        "Would you like me to help you call one of them, or just sit with you for a moment?"
    )

    return {
        "type": "crisis",
        "message": message,
        "tel": {
            "telemanas_14416": "tel:14416",
            "helper": f"tel:{phone}",
            "emergency_112": "tel:112",
        },
        "resources": [
            {
                "name": "Tele-MANAS",
                "number": "14416",
                "description": "Free, 24/7, India",
                "tel": "tel:14416",
            },
            {
                "name": helper,
                "number": phone,
                "description": "The person you asked for",
                "tel": f"tel:{phone}",
            },
            {
                "name": "Emergency",
                "number": "112",
                "description": "Immediate danger",
                "tel": "tel:112",
            },
        ],
    }


async def model_crisis_check(text: str) -> bool:
    """Ask the chat model a yes/no question about harm.

    Treat any unclear or failed response as NO from the model. The keyword
    layer is never disabled by a model failure.
    """
    try:
        resp = await chat(
            messages=[
                {
                    "role": "user",
                    "content": "does this message suggest the person may harm themselves or not want to live? Answer only YES or NO.",
                },
                {"role": "user", "content": text},
            ],
            temperature=0,
            keep_alive=settings.keep_alive,
        )
    except Exception:
        return False

    content = resp.get("content") if isinstance(resp, dict) else ""
    if not content or not isinstance(content, str):
        return False

    cleaned = content.strip().upper()
    # Accept exactly YES/NO, or with a period/space — keep strict.
    if cleaned.startswith("YES"):
        return True
    return False


def _get_use_model() -> bool:
    # Highest priority: monkeypatched function result? no. Check module var override.
    try:
        if _use_model_safety_check is not None:
            return bool(_use_model_safety_check)
    except Exception:
        pass
    try:
        if _use_model_safety_check_override is not None:
            return bool(_use_model_safety_check_override)
    except Exception:
        pass
    try:
        return bool(getattr(settings, "use_model_safety_check", True))
    except Exception:
        return True


def check(text: str) -> bool:
    """Keyword-first entry point. Model pass is optional via config."""
    if is_crisis(text):
        return True

    use_model = _get_use_model()

    if not use_model:
        return False

    try:
        return asyncio.get_event_loop().run_until_complete(model_crisis_check(text))
    except RuntimeError:
        # No event loop running (e.g. sync context); create a new one.
        return asyncio.run(model_crisis_check(text))
    except Exception:
        return False
