"""The tiny slice of config the browser is allowed to read."""

from __future__ import annotations

from fastapi import APIRouter

from app import config

router = APIRouter()


@router.get("/api/config")
async def public_config() -> dict[str, object]:
    # Only public copy and the friend's name, on purpose. Never helper_name,
    # helper_phone, the model names, or the admin passcode. A test pins the
    # exact key set. resting_message is human-written text meant to be shown.
    return {
        "friend_name": config.settings.friend_name,
        "moods": list(config.settings.moods),
        "resting_message": config.settings.resting_message,
    }
