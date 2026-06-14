"""KC-20 (#25): the Playwright e2e browser suite — shared harness.

These tests drive the REAL KimCad SPA in a real Chromium against a real `kimcad web --demo`
server (deterministic without Ollama or the slicer binaries, so the design path renders from the
template engine) — no DOM mocks, no stubbed APIs. The architecture is harvested from the
kimcadcodex e2e suite (live-server fixture + console-error watcher + the browser_serial marker),
rebuilt for this repo's stdlib `kimcad web` server (vs the codex uvicorn app).

Every e2e module sets `pytestmark = [pytest.mark.browser_serial, pytest.mark.needs_browser]`:
- `needs_browser` (root conftest) SKIPS the test when Chromium isn't installed, so a fresh clone
  or the hosted fork-PR smoke never hard-fails; the provisioned gate box runs them for real.
- `browser_serial` serializes them around the one shared localhost server.

The `page` fixture is pytest-playwright's built-in (a fresh browser context per test, so
localStorage — the first-run flag, saved designs, settings — starts clean every time).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Serialize browser_serial-marked tests around the one shared localhost server. Inert under the
# default single-process runner, but it makes the marker's contract explicit and keeps the suite
# correct if it is ever run under xdist.
_BROWSER_SERIAL_LOCK = threading.Lock()


@pytest.fixture(autouse=True)
def _serialize_browser_serial_tests(request: pytest.FixtureRequest) -> Iterator[None]:
    if request.node.get_closest_marker("browser_serial") is None:
        yield
    else:
        with _BROWSER_SERIAL_LOCK:
            yield

# Console messages that are environment noise, not SPA defects — a 4xx/5xx the SPA handles in its
# UI (e.g. a demo-mode endpoint returning 404) still surfaces as a browser "Failed to load
# resource" console error, and headless Chromium emits GL driver chatter. Anything else is a real
# console error/warning and fails the test.
_BENIGN_CONSOLE = (
    "Failed to load resource: the server responded",
    "GL Driver Message",
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def live_server() -> Iterator[str]:
    """Spawn a real `kimcad web --demo` server on a free loopback port and yield its base URL.

    Demo mode makes the design path deterministic without Ollama (the template engine renders),
    and the per-boot session-token guard (#31) is live — so the e2e exercises the genuine
    token-injection + SPA-header flow, not a bypass."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    process = subprocess.Popen(
        [sys.executable, "-m", "kimcad.cli", "web", "--host", "127.0.0.1",
         "--port", str(port), "--demo"],
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 45
    while time.time() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(
                f"`kimcad web --demo` exited before startup (code {exit_code})."
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.2)
    else:
        process.terminate()
        raise RuntimeError("`kimcad web --demo` did not start within 45s.")
    try:
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture
def console_errors(page) -> list[str]:  # noqa: ANN001 - `page` is pytest-playwright's fixture
    """Collect real browser console errors/warnings + uncaught page exceptions for the test.

    Attached before the test navigates, so a clean run ends with ``console_errors == []`` — the
    e2e contract that the SPA wires up without throwing, not merely that the right text rendered."""
    errors: list[str] = []
    page.on(
        "console",
        lambda message: errors.append(message.text)
        if message.type in {"error", "warning"}
        and not any(message.text.startswith(p) or p in message.text for p in _BENIGN_CONSOLE)
        else None,
    )
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    return errors
