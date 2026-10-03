"""PWA shell tests: home screen, manifest, icons, service worker and wiring.

These check the shipped static files, not just that they exist, so a broken
manifest or an accidental external resource fails the build. See AGENTS.md.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

from fastapi.testclient import TestClient

from app import main

BASE = Path(__file__).resolve().parent.parent
STATIC = BASE / "static"


def _client() -> TestClient:
    return TestClient(main.app)


def _flat(text: str) -> str:
    # Collapse whitespace so assertions survive pretty-printed HTML.
    return re.sub(r"\s+", " ", text)


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])


def test_home_screen_is_served_and_warm():
    r = _client().get("/")
    assert r.status_code == 200
    body = _flat(r.text)
    assert "How are you feeling?" in body
    assert "Want to tell me more?" in body
    assert "Log a win" in body
    assert "I have a challenge" in body
    assert "Show me another" in body
    assert (
        "This is a comfort tool, not therapy. If things feel too heavy, "
        "please reach out to someone." in body
    )


def test_home_links_shell_assets_and_they_all_load():
    client = _client()
    page = _flat(client.get("/").text)
    assert 'href="/manifest.json"' in page
    assert 'href="/app.css"' in page
    assert 'src="/app.js"' in page
    for path in [
        "/app.css",
        "/app.js",
        "/manifest.json",
        "/sw.js",
        "/404.html",
        "/icon-192.png",
        "/icon-512.png",
        "/icon-192-maskable.png",
        "/icon-512-maskable.png",
    ]:
        assert client.get(path).status_code == 200, path


def test_manifest_is_a_valid_pwa_manifest():
    m = _client().get("/manifest.json").json()
    assert m["id"] == "/"
    assert m["name"] == "Open When"
    assert m["short_name"] == "Open When"
    assert m["description"]
    assert m["display"] == "standalone"
    assert m["orientation"] == "portrait"
    assert m["scope"] == "/"
    assert m["start_url"] == "/"
    assert m["background_color"]
    assert m["theme_color"]
    assert {icon["sizes"] for icon in m["icons"]} == {"192x192", "512x512"}
    assert all(icon["type"] == "image/png" for icon in m["icons"])
    purposes = {icon.get("purpose") for icon in m["icons"]}
    assert "maskable" in purposes
    assert "any" in purposes


def test_icons_are_valid_pngs_at_the_right_size():
    client = _client()
    for name, size in (
        ("icon-192.png", 192),
        ("icon-512.png", 512),
        ("icon-192-maskable.png", 192),
        ("icon-512-maskable.png", 512),
    ):
        r = client.get("/" + name)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/png")
        assert _png_size(r.content) == (size, size), name


def test_home_head_has_install_and_status_bar_metadata():
    page = _flat((STATIC / "index.html").read_text(encoding="utf-8"))
    assert 'name="viewport"' in page
    assert "viewport-fit=cover" in page
    assert 'name="theme-color"' in page
    assert 'name="apple-mobile-web-app-capable"' in page
    assert 'name="apple-mobile-web-app-status-bar-style"' in page
    assert 'rel="apple-touch-icon"' in page
    assert 'name="mobile-web-app-capable"' in page


def test_home_has_welcome_install_and_update_surfaces():
    page = _flat((STATIC / "index.html").read_text(encoding="utf-8"))
    for needle in [
        'id="splash"',
        'id="welcome"',
        'id="welcomeNext"',
        'id="a2hs"',
        'id="a2hsAction"',
        'id="updateBanner"',
        'id="updateReload"',
    ]:
        assert needle in page, needle


def test_app_js_wires_the_endpoints_and_rotation():
    js = _flat((STATIC / "app.js").read_text(encoding="utf-8"))
    for needle in [
        "/api/feel",
        "/api/win",
        "/api/step",
        "recently_shown_ids",
        "sessionStorage",
        "/media/",
        "crisis",
        "resources",
        "tel:",
    ]:
        assert needle in js, needle


def test_app_js_wires_welcome_install_and_update():
    js = _flat((STATIC / "app.js").read_text(encoding="utf-8"))
    for needle in [
        "openwhen-welcome-v1",
        "openwhen-a2hs-v1",
        "beforeinstallprompt",
        "appinstalled",
        "display-mode: standalone",
        "SKIP_WAITING",
        "updateBanner",
    ]:
        assert needle in js, needle


def test_service_worker_never_caches_api_or_media():
    js = _flat((STATIC / "sw.js").read_text(encoding="utf-8"))
    assert 'indexOf("/api/")' in js
    assert 'indexOf("/media/")' in js
    shell = js[js.index("var SHELL = [") : js.index("];") + 2]
    assert "/api" not in shell
    assert "/media" not in shell


def test_service_worker_supports_the_update_handshake():
    js = _flat((STATIC / "sw.js").read_text(encoding="utf-8"))
    assert "/404.html" in js[js.index("var SHELL = [") : js.index("];") + 2]
    assert "SKIP_WAITING" in js
    assert "skipWaiting" in js


def test_service_worker_applies_updates_without_a_tap():
    # A worker that only waits on SKIP_WAITING leaves the friend stuck on an old
    # copy of the app. The install must skip waiting, and activate must reload
    # any page still running the previous files.
    js = _flat((STATIC / "sw.js").read_text(encoding="utf-8"))
    install = js[js.index('addEventListener("install"') : js.index('addEventListener("activate"')]
    assert "skipWaiting()" in install, "install must skip waiting"
    assert "client.navigate" in js, "activate must refresh open pages"
    assert "openwhen-shell-v6" in js


def test_unknown_path_serves_the_friendly_404_page():
    r = _client().get("/this-route-does-not-exist")
    assert r.status_code == 404
    assert "This page isn't here" in _flat(r.text)
    assert 'href="/"' in r.text


def test_home_has_a_saved_screen_and_a_subtle_status_line():
    page = _flat((STATIC / "index.html").read_text(encoding="utf-8"))
    for needle in [
        'id="saved"',
        'id="savedLead"',
        'id="savedList"',
        'id="savedEmpty"',
        'id="openSaved"',
        'id="status"',
        'id="statusText"',
        "status-dot",
    ]:
        assert needle in page, needle


def test_app_js_wires_favourites_offline_and_status():
    js = _flat((STATIC / "app.js").read_text(encoding="utf-8"))
    for needle in [
        "openwhen-favourites-v1",
        "CACHE_FAVORITE",
        "UNCACHE_FAVORITE",
        "fav-btn",
        "/api/health",
        "is-offline",
        "Showing what you saved",
        'addEventListener("offline"',
        'addEventListener("online"',
    ]:
        assert needle in js, needle


def test_app_js_remembers_recent_notes_for_the_resting_screen():
    js = _flat((STATIC / "app.js").read_text(encoding="utf-8"))
    for needle in [
        "openwhen-recent-v1",
        "openwhen-config-v1",
        "rememberRecent",
        "offlineMessages",
        "prefetchRecent",
        "/api/recent",
        "readCachedConfig",
        "writeCachedConfig",
        "SYNC_RECENT",
        "resting_message",
    ]:
        assert needle in js, needle


def test_service_worker_keeps_recent_voice_notes_for_offline():
    js = _flat((STATIC / "sw.js").read_text(encoding="utf-8"))
    assert "openwhen-recent-v1" in js
    assert "RECENT_CACHE" in js
    assert "SYNC_RECENT" in js
    # The recent cache must survive activation just like favourites.
    assert "key !== RECENT_CACHE" in js
    # Offline misses must return a real Response, and a non-root page must not
    # silently become the friend's screen.
    assert "offlineResponse" in js
    assert 'caches.match("/404.html")' in js


def test_service_worker_caches_favourites_and_serves_saved_media():
    js = _flat((STATIC / "sw.js").read_text(encoding="utf-8"))
    assert "openwhen-favourites-v1" in js
    assert "CACHE_FAVORITE" in js
    assert "UNCACHE_FAVORITE" in js
    assert "FAV_CACHE" in js
    # The favourites cache must survive activation.
    assert "key !== FAV_CACHE" in js
    # Saved voice notes are served from the favourites cache first.
    assert 'indexOf("/media/")' in js
    # Feelings and API responses are still never cached.
    assert 'indexOf("/api/")' in js


def test_app_js_registers_the_worker_first_and_guards_elements():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function bind(id, handler)" in js
    # Registration must happen before anything that could throw, so a stale
    # cached page can never stop offline support from coming up.
    assert js.index("registerServiceWorker();") < js.index('bind("send"')
    assert 'bind("openSaved"' in js


def test_service_worker_navigation_falls_back_to_the_shell():
    js = _flat((STATIC / "sw.js").read_text(encoding="utf-8"))
    assert 'request.mode === "navigate"' in js
    assert 'caches.match("/index.html")' in js
    assert 'caches.match("/")' in js


def test_shell_has_no_external_resources():
    for name in ("index.html", "app.css", "app.js", "sw.js", "404.html"):
        text = (STATIC / name).read_text(encoding="utf-8")
        for bad in ("http://", "https://", "//cdn"):
            assert bad not in text, f"{name} references {bad}"
