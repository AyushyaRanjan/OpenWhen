"""Watchdog: check the app's health and nudge the helper if it stops answering.

This runs on the helper's own machine, outside the friend-facing app. It never
reads, sends or logs anything the friend typed, felt, recorded or saved. The
only things it handles are a timestamp, the health result, and a fixed alert
line.

Alerts go only to the ntfy base URL from the config file, which defaults to a
self-hosted address on the local network. It must never be pointed at a cloud
service. See AGENTS.md.

Run it in a second terminal:

    .\\venv\\Scripts\\python.exe -m tools.watchdog
"""

from __future__ import annotations

import argparse
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from app.config import settings

log = logging.getLogger("openwhen.watchdog")

DEFAULT_INTERVAL = 5 * 60
REQUEST_TIMEOUT = 4.0

_ALERT_DOWN = (
    "Open When isn't answering. The little server on the laptop may have "
    "stopped, so please take a look when you can."
)
_ALERT_UP = "Open When is back up and answering again."


def check_health(url: str, timeout: float = REQUEST_TIMEOUT) -> bool:
    """True if the health endpoint answers with a 2xx. Never raises."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= int(response.status) < 300
    except Exception:
        # A down server is the normal thing this tool exists to notice, not an
        # exception to propagate.
        return False


def send_alert(
    base_url: str,
    topic: str,
    message: str,
    title: str = "Open When",
    timeout: float = REQUEST_TIMEOUT,
) -> bool:
    """POST a short plain-text note to ntfy. Returns whether it was accepted.

    With no topic configured this is a no-op, so the watchdog can run quietly
    until the helper sets one up.
    """
    base_url = (base_url or "").strip().rstrip("/")
    topic = (topic or "").strip()
    if not base_url or not topic:
        return False

    url = f"{base_url}/{urllib.parse.quote(topic)}"
    request = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Title": title,
            "Tags": "warning",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= int(response.status) < 300
    except Exception as exc:
        log.warning("Couldn't send the ntfy alert: %s", type(exc).__name__)
        return False


def run_once(was_down: bool) -> bool:
    """Run one health check.

    Alerts only when the state changes: once when it goes down, once when it
    comes back. `was_down` is the previous state; the return value is the new
    one.
    """
    healthy = check_health(settings.health_url)

    if not healthy and not was_down:
        log.warning("Health check failed; sending one alert.")
        send_alert(settings.ntfy_url, settings.ntfy_topic, _ALERT_DOWN)
    elif healthy and was_down:
        log.info("Back up; sending one recovery note.")
        send_alert(settings.ntfy_url, settings.ntfy_topic, _ALERT_UP, title="Open When")

    return not healthy


def run(interval: float = DEFAULT_INTERVAL, iterations: int | None = None) -> None:
    """Check in a loop. `iterations` is for tests; None means forever."""
    was_down = False
    count = 0
    while True:
        was_down = run_once(was_down)
        count += 1
        if iterations is not None and count >= iterations:
            return
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the Open When server and alert through ntfy if it is down."
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help="seconds between checks (default: 300)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="check once and exit, useful for a quick test",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.once:
        run(interval=0, iterations=1)
    else:
        run(interval=args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
