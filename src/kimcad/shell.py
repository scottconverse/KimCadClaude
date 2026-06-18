"""Stage 11 Slice 11.1 — the windowed app shell (`kimcad shell`).

A thin WebView2 window (pywebview, `edgechromium` backend — verified on this stack:
pywebview 6.2.1 / pythonnet 3.1.0 / the Win11-bundled WebView2 runtime, page-load proven)
over the EXISTING local server. The shell is a wrapper, never a fork of the serving logic:

- the server is the same handler `kimcad web` uses, bound to ``127.0.0.1`` on a **stable
  shell port** (8766, scanning a few up if taken — SHELL-001: the origin must be stable
  across launches or the SPA's localStorage — the first-run flag, client UI state — resets
  every time; an ephemeral port would silently wipe it each launch);
- the window's ``closed`` event shuts the server down — closing the app leaves no orphan
  process serving the design pipeline;
- external links open in the user's default browser, never inside the app window —
  exposed to the SPA as the ``window.pywebview.api.open_external`` bridge (the js_api).

pywebview is a Windows runtime dependency of the SHELL only: when it isn't importable
(a from-source install that never needed it), ``kimcad shell`` degrades to one friendly
line pointing at ``kimcad web`` — the browser path always works (graceful absence, the
CadQuery posture).
"""

from __future__ import annotations

import secrets
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:  # the shell's one optional dependency
    import webview
except ImportError:  # pragma: no cover - exercised via _set_webview_for_tests(None)
    webview = None  # type: ignore[assignment]

WINDOW_TITLE = "KimCad"
# SHELL-001: a STABLE origin across launches. 8766 (one above the dev default, which stays
# free for a side-by-side `kimcad web`), scanning a small fixed range if taken. NEVER an
# ephemeral port — a new origin every launch wipes the SPA's localStorage (first-run flag,
# client UI state) and re-runs the wizard forever.
SHELL_PORTS = tuple(range(8766, 8776))


def open_external(url: str) -> None:
    """Open ``url`` in the system default browser (never inside the app window). Only
    http(s) — checked case-insensitively (SHELL-008); anything else is refused quietly
    (the SPA has no business opening other schemes)."""
    if isinstance(url, str) and url.strip().lower().startswith(("http://", "https://")):
        webbrowser.open(url.strip())


class _JsApi:
    """The bridge the SPA reaches as ``window.pywebview.api`` (SHELL-004: actually wired,
    not just documented). One method on purpose — the window is a viewport, not an RPC
    surface."""

    def open_external(self, url: str) -> None:
        open_external(url)


def _webview_storage_dir() -> Path:
    """Where the WebView2 profile lives (SHELL-005): our own app dir, not the shared
    ``%APPDATA%\\pywebview`` default — so the uninstaller can find it and other pywebview
    apps can't share our profile. Routed through the Slice-11.4 paths seam."""
    from kimcad.paths import webview_profile_dir

    return webview_profile_dir()


def build_shell(
    *,
    demo: bool = False,
    backend: str | None = None,
    start_gui: bool = True,
) -> ThreadingHTTPServer:
    """Start the server on the stable shell port, open the app window over it, and
    (when ``start_gui``) block until the window closes. Returns the server so tests can
    assert on (and clean up) the non-GUI parts."""
    if webview is None:
        raise RuntimeError(
            "KimCad's app window needs the pywebview package, which isn't installed. "
            "Run `pip install pywebview` — or use the browser instead: run `kimcad web` "
            "and open the address it prints."
        )

    from kimcad.config import Config
    from kimcad.webapp import _ExclusiveBindServer, build_web_pipeline, make_handler

    config = Config.load()
    pipeline = build_web_pipeline(demo=demo, backend=backend)
    from kimcad.paths import output_dir

    web_root = output_dir() / "web"  # SHELL-006 closed: routed through the 11.4 seam
    # #31 (KC-26): the desktop shell is the primary distribution, so it gets the SAME per-boot
    # session-token guard as `kimcad web` (serve()). The WebView2 navigates to the loopback HTTP
    # URL below, so the server injects this token into the served shell and the SPA returns it on
    # state-changing requests — a drive-by cross-origin POST (which can't read it) is refused.
    session_token = secrets.token_urlsafe(32)
    handler = make_handler(pipeline, web_root, config=config, session_token=session_token)
    httpd: ThreadingHTTPServer | None = None
    for candidate in SHELL_PORTS:
        try:
            httpd = _ExclusiveBindServer(("127.0.0.1", candidate), handler)
            break
        except OSError:
            continue
    if httpd is None:
        raise RuntimeError(
            f"KimCad's app ports ({SHELL_PORTS[0]}-{SHELL_PORTS[-1]}) are all in use - "
            "is another KimCad window already open? Close it, or run `kimcad web` on a "
            "port of your choice."
        )
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    # UX-COLD-001: the windowed app is the primary distribution, so it auto-starts a managed Ollama
    # off the launch path too (best-effort; see serve()). Skipped in demo mode (no LLM).
    if not demo:
        from kimcad.ollama_runtime import ensure_serving_background

        ensure_serving_background()

    url = f"http://127.0.0.1:{port}/"
    window = webview.create_window(
        WINDOW_TITLE,
        url,
        js_api=_JsApi(),
        width=1280,
        height=860,
        min_size=(900, 600),
    )

    def _on_closed() -> None:
        # The window IS the app: closing it stops the server (no orphan pipeline server) AND the
        # managed Ollama child KimCad started (ENG-GG-001 — never an orphan headless serve).
        httpd.shutdown()
        try:
            from kimcad.ollama_runtime import stop_managed

            stop_managed()
        except Exception:  # noqa: BLE001 — teardown is best-effort; window close must not raise
            pass

    window.events.closed += _on_closed
    if start_gui:
        # Blocks until the window closes. `edgechromium` = WebView2 (the controlled render
        # engine the spec names); private_mode False + our own storage_path so the SPA's
        # localStorage (first-run flag, saved UI state) survives restarts like a normal
        # app, in a profile dir the uninstaller can name (SHELL-005).
        try:
            # Kim Everywhere: title bar + taskbar + Alt-Tab thumbnail use Kim's branded ico,
            # shipped in src/kimcad/web/kim.ico. Silently skipped if the file is missing.
            _icon_path = Path(__file__).resolve().parent / "web" / "kim.ico"
            _start_kwargs: dict[str, object] = {
                "gui": "edgechromium",
                "private_mode": False,
                "storage_path": str(_webview_storage_dir()),
            }
            if _icon_path.is_file():
                _start_kwargs["icon"] = str(_icon_path)
            webview.start(**_start_kwargs)
        except KeyboardInterrupt:  # SHELL-009: Ctrl+C in the console = close, not a traceback
            pass
        except Exception as e:  # SHELL-003: a missing WebView2 runtime must end friendly
            httpd.shutdown()
            httpd.server_close()
            raise RuntimeError(
                "KimCad's app window couldn't start - the Microsoft WebView2 runtime or "
                ".NET Framework 4.7.2+ may be missing (both ship with Windows 11; on "
                "older Windows, install 'WebView2 Runtime' from Microsoft). The browser "
                f"always works instead: run `kimcad web`. Detail: {e}"
            ) from e
        # SHELL-002: stop the serve loop BEFORE closing the socket — closing under a live
        # serve_forever raises WinError 10038 in the daemon thread. shutdown() is a no-op
        # if the closed event already fired.
        httpd.shutdown()
        httpd.server_close()
    return httpd


def _set_webview_for_tests(fake: Any) -> Any:
    """Test seam: swap the webview module object; returns the previous one."""
    global webview
    prev = webview
    webview = fake
    return prev
