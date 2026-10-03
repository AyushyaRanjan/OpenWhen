"""Tests for tools/watchdog.py. All network calls are mocked.

The watchdog must never send or log anything the friend typed; these tests also
pin that it only ever posts fixed alert lines.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tools import watchdog


class _Response:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _settings(**overrides: object) -> SimpleNamespace:
    base = {
        "health_url": "http://127.0.0.1:8000/api/health",
        "ntfy_url": "http://127.0.0.1:8080",
        "ntfy_topic": "openwhen",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_check_health_true_on_2xx(monkeypatch):
    monkeypatch.setattr(
        watchdog.urllib.request, "urlopen", lambda url, timeout=None, **kw: _Response(200)
    )
    assert watchdog.check_health("http://127.0.0.1:8000/api/health") is True


def test_check_health_false_on_error(monkeypatch):
    def boom(url, timeout=None, **kw):
        raise OSError("connection refused")

    monkeypatch.setattr(watchdog.urllib.request, "urlopen", boom)
    assert watchdog.check_health("http://127.0.0.1:8000/api/health") is False


def test_send_alert_is_a_noop_without_a_topic(monkeypatch):
    def explode(*a, **k):
        raise AssertionError("urlopen must not be called without a topic")

    monkeypatch.setattr(watchdog.urllib.request, "urlopen", explode)
    assert watchdog.send_alert("http://127.0.0.1:8080", "", "hello") is False


def test_send_alert_posts_plain_text_to_the_topic(monkeypatch):
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=None, **kw):
        captured["url"] = request.full_url
        captured["data"] = request.data
        captured["method"] = request.method
        return _Response(200)

    monkeypatch.setattr(watchdog.urllib.request, "urlopen", fake_urlopen)
    ok = watchdog.send_alert(
        "http://127.0.0.1:8080/", "my-topic", "server is down"
    )

    assert ok is True
    assert captured["url"] == "http://127.0.0.1:8080/my-topic"
    assert captured["method"] == "POST"
    assert captured["data"] == b"server is down"


def test_send_alert_returns_false_when_ntfy_rejects(monkeypatch):
    def boom(request, timeout=None, **kw):
        raise OSError("unreachable")

    monkeypatch.setattr(watchdog.urllib.request, "urlopen", boom)
    assert watchdog.send_alert("http://127.0.0.1:8080", "t", "x") is False


def test_run_once_alerts_once_when_going_down(monkeypatch):
    alerts: list[str] = []
    monkeypatch.setattr(watchdog, "settings", _settings())
    monkeypatch.setattr(watchdog, "check_health", lambda url, timeout=None: False)
    monkeypatch.setattr(
        watchdog, "send_alert", lambda *a, **k: alerts.append(a[2]) or True
    )

    now_down = watchdog.run_once(was_down=False)

    assert now_down is True
    assert len(alerts) == 1


def test_run_once_stays_quiet_while_already_down(monkeypatch):
    alerts: list[str] = []
    monkeypatch.setattr(watchdog, "settings", _settings())
    monkeypatch.setattr(watchdog, "check_health", lambda url, timeout=None: False)
    monkeypatch.setattr(
        watchdog, "send_alert", lambda *a, **k: alerts.append(a[2]) or True
    )

    now_down = watchdog.run_once(was_down=True)

    assert now_down is True
    assert alerts == []


def test_run_once_alerts_once_on_recovery(monkeypatch):
    alerts: list[str] = []
    monkeypatch.setattr(watchdog, "settings", _settings())
    monkeypatch.setattr(watchdog, "check_health", lambda url, timeout=None: True)
    monkeypatch.setattr(
        watchdog, "send_alert", lambda *a, **k: alerts.append(a[2]) or True
    )

    now_down = watchdog.run_once(was_down=True)

    assert now_down is False
    assert len(alerts) == 1


def test_run_once_silent_when_healthy_and_still_up(monkeypatch):
    alerts: list[str] = []
    monkeypatch.setattr(watchdog, "settings", _settings())
    monkeypatch.setattr(watchdog, "check_health", lambda url, timeout=None: True)
    monkeypatch.setattr(
        watchdog, "send_alert", lambda *a, **k: alerts.append(a[2]) or True
    )

    assert watchdog.run_once(was_down=False) is False
    assert alerts == []


def test_run_checks_the_expected_number_of_times(monkeypatch):
    calls: list[bool] = []
    monkeypatch.setattr(watchdog.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        watchdog, "run_once", lambda was_down: calls.append(was_down) or was_down
    )

    watchdog.run(interval=0, iterations=3)

    assert calls == [False, False, False]


def test_alert_lines_are_fixed_and_single_line():
    assert "\n" not in watchdog._ALERT_DOWN
    assert "\n" not in watchdog._ALERT_UP
    assert watchdog._ALERT_DOWN.strip()
    assert watchdog._ALERT_UP.strip()
