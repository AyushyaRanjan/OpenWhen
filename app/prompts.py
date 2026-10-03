"""Load the editable prompts from the prompts/ folder.

Prompts live in plain text files so they can be improved without touching code.
Files are read on each call on purpose: editing a prompt takes effect on the
next request, no restart needed. If a file is missing or empty we fall back to
a small safe default rather than sending a model an empty system prompt.
See AGENTS.md.
"""

from __future__ import annotations

import logging

from app.config import BASE_DIR

log = logging.getLogger(__name__)

PROMPTS_DIR = BASE_DIR / "prompts"

# Kept deliberately short. These are only used if the real file is gone.
_FALLBACK = {
    "lead_in": (
        "Write one or two warm, plain sentences that introduce the provided "
        "messages and wins. Never invent facts and never claim to be human."
    ),
    "tiny_step": (
        "Offer one tiny, kind, practical step for right now in at most two "
        "short sentences. Never invent facts and never claim to be human."
    ),
}


def load(name: str) -> str:
    """Return prompts/<name>.txt, or a safe fallback if it is missing/empty."""
    path = PROMPTS_DIR / f"{name}.txt"
    try:
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    except OSError:
        pass

    # Never log file contents; only which prompt could not be read.
    log.warning("Prompt file %s.txt was missing or empty; using the fallback.", name)
    return _FALLBACK.get(name, "")
