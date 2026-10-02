"""Settings for the whole app, loaded once from a JSON file in the repo root."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
EXAMPLE_CONFIG_PATH = BASE_DIR / "config.example.json"

REQUIRED_KEYS = (
    "chat_model",
    "embed_model",
    "ollama_url",
    "friend_name",
    "helper_name",
    "helper_phone",
    "moods",
    "min_match_score",
    "keep_alive",
    "use_model_safety_check",
)


@dataclass(frozen=True)
class Settings:
    """Every setting the app needs. Frozen so nothing can change it at runtime."""

    chat_model: str
    embed_model: str
    ollama_url: str
    friend_name: str
    helper_name: str
    helper_phone: str
    moods: list[str]
    min_match_score: float
    keep_alive: str
    use_model_safety_check: bool = True


def _resolve_config_path() -> Path:
    """Prefer the real config, fall back to the example so the app still starts."""
    if CONFIG_PATH.exists():
        return CONFIG_PATH

    log.warning(
        "No config.json here yet, so I'm using config.example.json for now. "
        "To make it yours: Copy-Item config.example.json config.json"
    )
    if not EXAMPLE_CONFIG_PATH.exists():
        raise RuntimeError(
            "Neither config.json nor config.example.json is present. "
            "Restore config.example.json from git and try again."
        )
    return EXAMPLE_CONFIG_PATH


def load_settings() -> Settings:
    path = _resolve_config_path()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{path.name} isn't valid JSON (problem on line {exc.lineno}). "
            "Fix the typo, or delete the file and copy config.example.json again."
        ) from exc

    missing = [key for key in REQUIRED_KEYS if key not in raw]
    if missing:
        raise RuntimeError(
            f"{path.name} is missing these: {', '.join(missing)}. "
            "Copy config.example.json again and fill them in."
        )

    return Settings(
        chat_model=raw["chat_model"],
        embed_model=raw["embed_model"],
        ollama_url=raw["ollama_url"],
        friend_name=raw["friend_name"],
        helper_name=raw["helper_name"],
        helper_phone=raw["helper_phone"],
        moods=list(raw["moods"]),
        min_match_score=float(raw["min_match_score"]),
        keep_alive=raw["keep_alive"],
        use_model_safety_check=bool(raw.get("use_model_safety_check", True)),
    )


settings = load_settings()
