"""KC-20 (#25): the Playwright e2e browser suite — shared harness.

These tests drive the REAL TinkerQuarry SPA in a real Chromium against a real `kimcad web --demo`
server (deterministic without Ollama or the slicer binaries, so the design path renders from the
template engine) — no DOM mocks, no stubbed APIs. The architecture is harvested from the
kimcadcodex e2e suite (live-server fixture + console-error watcher + the browser_serial marker),
rebuilt for this repo's stdlib `kimcad web` server (vs the codex uvicorn app).

Markers: the harness/UI modules (test_smoke, test_wizard) carry
`[browser_serial, needs_browser]`; the design-TRIGGERING modules
(test_design_refine, test_onramps, test_export_gate, and the design tests in
test_settings_designs) ADD `real_tool` because demo mode still renders with the real OpenSCAD
binary (and slices with OrcaSlicer) — so they skip cleanly where the binaries are absent.
- `needs_browser` (root conftest) SKIPS when Chromium isn't installed (fresh clone / fork-PR smoke);
  the provisioned gate runs them for real.
- `real_tool` SKIPS when OpenSCAD/OrcaSlicer aren't fetched.
- `browser_serial` serializes the tests; it is an in-process lock and so requires SINGLE-PROCESS
  runs (it does NOT serialize across xdist workers — see the marker note).

SCOPE: the suite always runs `--demo`, so the LLM→plan path and the cloud-routing
_SettingsAwareProvider are deliberately OUT of e2e scope (the template render + slice plumbing IS
in scope). The real model path is covered by the unit/benchmark suites, not here.

The pytest-playwright `page` fixture resets BROWSER state (localStorage/cookies) per test. But the
`live_server` is session-scoped, so SERVER-side state — saved designs, settings — PERSISTS across
the session in the isolated home; journeys that care use a distinctive/unique prompt or restore
the setting they changed (see the per-test notes).
"""

from __future__ import annotations

import base64
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

# A minimal valid 1x1 PNG. The photo/sketch on-ramp accepts any image and, in demo mode, ignores
# its content (DemoProvider.describe_photo/sketch return a canned seed) — so this stand-in is all
# the upload journeys need.
_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The localStorage flag App.tsx reads to decide whether to show the first-run wizard (App.tsx:90:
# `localStorage.getItem('kc-first-run-done') !== '1'`). Seeding it pre-navigation suppresses the
# wizard so the design/refine/slider journeys reach the workspace; the onboarding journey omits it.
_FIRST_RUN_DONE = "window.localStorage.setItem('kc-first-run-done', '1')"

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

# Headless Chromium emits GL-driver perf chatter as console warnings — genuine environment noise.
# Everything else (incl. a "Failed to load resource" from a 4xx/5xx) is treated as a real defect:
# demo mode serves every route the journeys hit (favicon is a 204), so a resource-load error means
# either a masked broken API call the SPA swallowed or a missing committed asset — exactly what an
# e2e should catch (TEST-1 / QA-7, audit-team 2026-06-14). The deliberately-mocked 500s in the
# error-recovery journeys are client-fulfilled and those tests don't assert console_errors == [].
_BENIGN_CONSOLE = (
    "GL Driver Message",
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def live_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Spawn a real `kimcad web --demo` server on a free loopback port and yield its base URL.

    Demo mode makes the design path deterministic without Ollama (the template engine renders),
    and the per-boot session-token guard (#31) is live — so the e2e exercises the genuine
    token-injection + SPA-header flow, not a bypass.

    FULLY ISOLATED state: the server's home is redirected to a throwaway dir (designs/history/
    settings land there, never the real ~/.kimcad — Path.home() resolves via USERPROFILE on
    Windows, HOME elsewhere), AND `--out <home>/output` redirects the render artifacts (meshes/
    slices) there too, never the developer's repo `output/` tree. The dir is discarded with the
    session. NOTE the server is SESSION-scoped, so server-side state (settings, the designs store)
    persists ACROSS the session's journeys — see the per-test notes for the unique-prompt /
    restore-the-setting workarounds."""
    home = tmp_path_factory.mktemp("kimcad_home")
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "PYTHONPATH": str(_REPO_ROOT / "src"),
        "USERPROFILE": str(home),
        "HOME": str(home),
    }
    # Capture the child's stdout+stderr to a file (a PIPE could deadlock on a long-lived server) so
    # a genuine startup failure carries the real traceback / the friendly 'port in use' line, not a
    # bare exit code (QA-2 / ENG-8, audit-team 2026-06-14).
    log_path = home / "server.log"
    log = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "kimcad.cli", "web", "--host", "127.0.0.1",
         "--port", str(port), "--demo", "--out", str(home / "output")],
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )

    def _server_log() -> str:
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-15:]
            return ("\n  " + "\n  ".join(tail)) if tail else " (no server output captured)"
        except OSError:
            return " (server log unavailable)"

    try:
        deadline = time.time() + 45
        while time.time() < deadline:
            exit_code = process.poll()
            if exit_code is not None:
                raise RuntimeError(
                    f"`kimcad web --demo` exited before startup (code {exit_code}). "
                    f"Server output:{_server_log()}"
                )
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            process.terminate()
            raise RuntimeError(
                f"`kimcad web --demo` did not start within 45s. Server output:{_server_log()}"
            )
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)  # reap the hard-killed process (ENG-7)
        log.close()


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


@pytest.fixture
def landing(page: Page, live_server: str, console_errors: list[str]) -> Page:
    """A page at the landing with the first-run wizard suppressed and the console watcher already
    attached (it depends on console_errors, so the watcher is in place BEFORE navigation)."""
    page.add_init_script(_FIRST_RUN_DONE)
    page.goto(live_server)
    return page


@pytest.fixture
def sample_image(tmp_path: Path) -> str:
    """A real on-disk image for the photo/sketch upload journeys (content is ignored in demo)."""
    p = tmp_path / "sample.png"
    p.write_bytes(_PNG_1x1)
    return str(p)


@pytest.fixture
def design(landing: Page):  # noqa: ANN201 - returns a callable
    """A helper that submits a prompt from the landing and waits for the design workspace to
    render (the demo template engine renders deterministically, no model needed). Returns the
    designed page so journeys can assert on / interact with the result."""
    def _design(prompt: str = "a 40 mm desk cable clip") -> Page:
        landing.get_by_label("Describe the part you want").fill(prompt)
        landing.get_by_role("button", name="Design it").click()
        landing.wait_for_url("**/design/**", timeout=30_000)
        # The Parameters tab appears only once the real OpenSCAD render lands — a generous timeout
        # so a cold/under-load render (the gate box thermally throttles) never flakes the suite.
        expect(landing.get_by_role("tab", name="Parameters")).to_be_visible(timeout=30_000)
        return landing

    return _design


@pytest.fixture
def design_prompt(landing: Page):  # noqa: ANN201 - returns a callable
    """Submit a prompt from the landing WITHOUT waiting for the design route — for flows that
    don't go straight to a part (e.g. demo:gatefail, which first offers the experimental
    generator in the conversation). Returns the page for the caller to assert on."""
    def _submit(prompt: str) -> Page:
        landing.get_by_label("Describe the part you want").fill(prompt)
        landing.get_by_role("button", name="Design it").click()
        return landing

    return _submit
