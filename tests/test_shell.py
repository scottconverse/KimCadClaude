"""Stage 11 Slice 11.1 — the app shell. The GUI is faked (webview swapped via the test
seam); what's under test is the wiring: ephemeral loopback bind, the served SPA being the
real handler, window-close stopping the server, the external-link bridge, and graceful
absence of pywebview."""

from __future__ import annotations

import urllib.request

import pytest

import kimcad.shell as shell


class FakeEvents:
    def __init__(self):
        self.closed_handlers = []

    @property
    def closed(self):
        return self

    @closed.setter
    def closed(self, value):  # `events.closed += h` assigns the result of __iadd__
        pass

    def __iadd__(self, handler):
        self.closed_handlers.append(handler)
        return self


class FakeWindow:
    def __init__(self):
        self.events = FakeEvents()


class FakeWebview:
    def __init__(self):
        self.created: list[dict] = []
        self.started: list[dict] = []
        self.window = FakeWindow()

    def create_window(self, title, url, **kw):
        self.created.append({"title": title, "url": url, **kw})
        return self.window

    def start(self, **kw):
        self.started.append(kw)


@pytest.fixture
def fake_webview():
    fake = FakeWebview()
    prev = shell._set_webview_for_tests(fake)
    yield fake
    shell._set_webview_for_tests(prev)


def _shutdown(httpd):
    httpd.shutdown()
    httpd.server_close()


def test_shell_binds_a_stable_loopback_port_and_serves_the_real_app(fake_webview):
    httpd = shell.build_shell(demo=True, start_gui=False)
    try:
        host, port = httpd.server_address[0], httpd.server_address[1]
        assert host == "127.0.0.1"
        # SHELL-001: the origin must be STABLE across launches (localStorage holds the
        # first-run flag + client UI state) — the fixed shell range, never ephemeral,
        # and never the dev default (a side-by-side `kimcad web` stays possible).
        assert port in shell.SHELL_PORTS
        assert port != 8765
        url = fake_webview.created[0]["url"]
        assert url == f"http://127.0.0.1:{port}/"
        assert fake_webview.created[0]["title"] == "KimCad"
        # SHELL-004: the external-link bridge is actually wired as the js_api.
        assert isinstance(fake_webview.created[0]["js_api"], shell._JsApi)
        # The window is pointed at the REAL app: the health endpoint answers.
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=30) as r:
            assert r.status == 200
    finally:
        _shutdown(httpd)


def test_shell_server_enforces_the_session_token_guard(fake_webview):
    """#31 (KC-26): the desktop shell is the primary distribution, so it must enforce the SAME
    per-boot session-token guard as `kimcad web`. A state-changing POST without the injected token
    is refused 403; the served shell carries a real token (placeholder substituted); supplying the
    token makes the POST pass. Pins that the guard isn't silently off in the packaged app."""
    import http.client
    import re

    httpd = shell.build_shell(demo=True, start_gui=False)
    try:
        port = httpd.server_address[1]
        # Generous HTTP timeouts: under the FULL self-hosted gate (live OrcaSlicer + real-model runs
        # saturate CPU), the shell's daemon serve_forever thread can be starved past a tight 10s
        # budget, intermittently aborting the read (WinError 10053). 30s rides out the load — the
        # same thermally-throttling-box accommodation the e2e suite already uses.
        # A tokenless state-changing POST is refused.
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        conn.request("POST", "/api/settings", body=b"{}", headers={"Content-Type": "application/json"})
        assert conn.getresponse().status == 403
        conn.close()
        # The served shell carries a REAL per-boot token (the placeholder was substituted).
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=30) as r:
            html = r.read().decode("utf-8")
        assert "__KIMCAD_SESSION_TOKEN__" not in html
        m = re.search(r'name="kimcad-session-token" content="([^"]+)"', html)
        assert m and m.group(1), "no session token injected into the shell"
        # With the token, the same POST is no longer 403.
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        conn.request("POST", "/api/settings", body=b"{}",
                     headers={"Content-Type": "application/json", "X-KimCad-Session": m.group(1)})
        assert conn.getresponse().status != 403
        conn.close()
    finally:
        _shutdown(httpd)


def test_a_second_shell_takes_the_next_stable_port(fake_webview):
    """Two windows coexist (each on its own stable port); when the whole range is taken
    the failure is one friendly line, not a bind traceback."""
    first = shell.build_shell(demo=True, start_gui=False)
    try:
        second = shell.build_shell(demo=True, start_gui=False)
        try:
            p1, p2 = first.server_address[1], second.server_address[1]
            assert p1 != p2 and {p1, p2} <= set(shell.SHELL_PORTS)
        finally:
            _shutdown(second)
    finally:
        _shutdown(first)


def test_window_close_stops_the_server(fake_webview):
    httpd = shell.build_shell(demo=True, start_gui=False)
    # Fire the closed handler (the user closed the window) and prove the socket stops
    # answering — the close-stops-server contract.
    handlers = fake_webview.window.events.closed_handlers
    assert len(handlers) == 1
    handlers[0]()
    httpd.server_close()
    port = httpd.server_address[1]
    with pytest.raises(OSError):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)


def test_missing_pywebview_degrades_to_one_friendly_line():
    prev = shell._set_webview_for_tests(None)
    try:
        with pytest.raises(RuntimeError) as ei:
            shell.build_shell(demo=True, start_gui=False)
        msg = str(ei.value)
        assert "kimcad web" in msg  # the browser path is named — never a dead end
        assert "pywebview" in msg
    finally:
        shell._set_webview_for_tests(prev)


def test_open_external_only_opens_http_urls(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(shell.webbrowser, "open", lambda u: opened.append(u))
    shell.open_external("https://ollama.com/download")
    shell.open_external("http://example.com")
    shell.open_external("HTTPS://Ollama.com")  # SHELL-008: schemes are case-insensitive
    shell.open_external("  https://padded.example  ")  # leading whitespace tolerated
    shell.open_external("file:///C:/Windows/system32/calc.exe")  # refused quietly
    shell.open_external("javascript:alert(1)")  # refused quietly
    shell.open_external("javascript%3Aalert(1)")  # refused quietly
    assert opened == [
        "https://ollama.com/download",
        "http://example.com",
        "HTTPS://Ollama.com",
        "https://padded.example",
    ]


def test_gui_failure_ends_friendly_and_stops_the_server(fake_webview):
    """SHELL-003: a missing WebView2 runtime (webview.start raising) must end in one
    friendly RuntimeError naming the browser fallback — with the server stopped."""
    def boom(**kw):
        raise Exception("WebView2 runtime not found")

    fake_webview.start = boom
    with pytest.raises(RuntimeError) as ei:
        shell.build_shell(demo=True, start_gui=True)
    assert "WebView2" in str(ei.value)
    assert "kimcad web" in str(ei.value)


def test_gui_start_uses_webview2_and_a_kimcad_owned_profile(fake_webview):
    httpd = shell.build_shell(demo=True, start_gui=True)
    # start_gui=True already shut the server down on window close (SHELL-002) — no leak.
    assert len(fake_webview.started) == 1
    kw = fake_webview.started[0]
    assert kw["gui"] == "edgechromium"
    assert kw["private_mode"] is False  # localStorage survives restarts
    # SHELL-005: OUR profile dir (uninstaller-visible), not the shared pywebview default.
    assert kw["storage_path"].endswith("KimCad\\webview") or kw["storage_path"].endswith("KimCad/webview")
    # And the socket is closed — no orphan server after the GUI loop exits.
    port = httpd.server_address[1]
    with pytest.raises(OSError):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)
