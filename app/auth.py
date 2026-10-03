"""Admin passcode check for the routes that list and delete items.

The passcode is read from config and arrives in a request header. It must never
appear in a URL — uvicorn's access log records the full path including the query
string — and it must never be logged.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app import config


async def require_admin(x_admin_passcode: str | None = Header(default=None)) -> None:
    """Allow the request only if it carries the configured admin passcode.

    An empty configured passcode means admin is switched off, not open. Failing
    closed is the only safe default: otherwise a fresh clone with no passcode
    would expose every message the friend has.
    """
    expected = str(getattr(config.settings, "admin_passcode", "") or "")

    if not expected:
        raise HTTPException(
            status_code=401,
            detail="Admin isn't set up yet. Add an admin_passcode in config.json.",
        )

    if x_admin_passcode is None or not hmac.compare_digest(x_admin_passcode, expected):
        raise HTTPException(status_code=401, detail="That passcode didn't match.")
