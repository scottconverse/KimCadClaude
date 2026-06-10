# Audit-lite — Stage 11 Slice 11.1: the windowed app shell (`kimcad shell`)

- **Date:** 2026-06-10
- **Auditor:** Claude (independent single-pass audit-lite)
- **Scope:** uncommitted working-tree changes for Slice 11.1 ONLY — `src/kimcad/shell.py` (new),
  `tests/test_shell.py` (new), the `shell` subcommand hunks in `src/kimcad/cli.py`, and the
  pywebview pins in `pyproject.toml` + `requirements.lock`. The Stage-10 gate-remediation
  hunks elsewhere in the same working tree were audited separately and are excluded.
- **Plan:** `.claude/plans/stage-11-installer-beta.md`, Slice 11.1 section.

## Verification actually run

| Check | Result |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest tests/test_shell.py tests/test_cli.py -q` | **36 passed**, 1 warning (`PytestUnhandledThreadExceptionWarning`, root-caused below → SHELL-002) |
| `ruff check shell.py test_shell.py cli.py` | clean |
| `ruff format --check` (same files) | `cli.py` would reformat — **all 4 hunks are pre-existing Stage-10/older lines** (~303, ~382, ~410, ~534), none in the 11.1 hunks; out of scope, noted for the Stage-10 set |
| `pip freeze` vs `requirements.lock` | all 7 new pins match exactly (bottle 0.13.4, cffi 2.0.0, clr-loader 0.3.1, proxy-tools 0.1.0, pycparser 3.0, pythonnet 3.1.0, pywebview 6.2.1) |
| pycparser==3.0 real? | yes — installed dist-info says 3.0 and PyPI confirms 3.0 is the current release (cffi 2.0 moved to it); not a typo of 2.x |
| pyproject marker | `'pywebview>=6.2; sys_platform == "win32"'` — valid PEP 508 |
| pywebview profile path (read from installed 6.2.1 source) | with `private_mode=False` and no `storage_path`, `winforms.init_storage()` puts the WebView2 UserDataFolder at `%APPDATA%\pywebview` — **writable, NOT Program Files** (no installer break), but see SHELL-005 |
| SPA localStorage usage | `kc-first-run-done` + one other key in `src/kimcad/web/assets/kimcad.js` — load-bearing for SHELL-001 |

## Severity roll-up

| Severity | Count |
| --- | --- |
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 5 |
| Nit | 3 |

## Findings

### SHELL-001 — Major — Ephemeral port defeats the localStorage persistence that `private_mode=False` exists to provide
`src/kimcad/shell.py:69` binds port 0 (a different port every launch) and `:91` sets
`private_mode=False` with the stated purpose "so localStorage (saved designs' UI state, the
first-run flag) survives restarts like a normal app." localStorage is **origin-scoped**, and the
origin is `http://127.0.0.1:<port>` — the port changes every launch, so every shell launch is a
fresh origin. Concretely: the SPA's `kc-first-run-done` flag (`web/assets/kimcad.js`) never
matches, so **the first-run wizard reappears on every single launch of the windowed app**, and
any other localStorage UI state is silently lost between runs. The disk profile persists; the
app just can never find its own data again. The plan locked the ephemeral port (collision
avoidance — sound), so the fix is on the state side, e.g.: (a) prefer a fixed shell port
(e.g. 8766) and fall back to ephemeral only on bind failure; (b) move the first-run flag and UI
state server-side (settings_store already exists); or (c) seed/readback via a js_api bridge.
Until one lands, `private_mode=False` buys nothing the app can use, and the headline first-run
UX of the installer's entry point is broken. (The live verification recorded for this slice
exercised one launch — a single launch cannot see this.)

### SHELL-002 — Minor — `server_close()` without `shutdown()` when the closed handler never fired (the pytest thread-exception warning, root-caused)
`src/kimcad/shell.py:91-92`: after `webview.start()` returns, `httpd.server_close()` runs
unconditionally — but `httpd.shutdown()` only runs if the window's `closed` event fired. If
`start()` returns without the event (window/WebView2 crash; or the fake no-op `start` in
`test_gui_start_uses_webview2_and_persistent_profile`), the listening socket is closed under a
live `serve_forever()` loop, whose selector then raises `OSError [WinError 10038] not a socket`
in the daemon thread. That is exactly the `PytestUnhandledThreadExceptionWarning` seen in the
run (attributed to a later `test_cli` test only because the daemon thread dies asynchronously,
within `poll_interval`). Not vestigial test noise — it is the production crash-path ordering
hazard surfacing through the seam. Fix is one line: call `httpd.shutdown()` before
`server_close()` after `start()` returns; `shutdown()` is idempotent here (`__is_shut_down`
stays set), so the normal closed-event path is unaffected and the warning disappears.

### SHELL-003 — Minor — `webview.start()` raising bypasses every friendly handler → raw traceback (WebView2-runtime-missing case)
pywebview's `WebViewException` subclasses plain `Exception`, not `RuntimeError`
(`webview/errors.py`), so a failed GUI start (WebView2 runtime missing/corrupt — plausible on
Win10/Server beta boxes; Win11 bundles it) propagates through `cli.py` main's handlers
(`:578-616`: RuntimeError → friendly; generic except → model-unreachable checks → re-raise) and
ends in a raw traceback, exactly the first-run failure class the CLI elsewhere refuses to show.
No orphan **process** results — the serve thread is a daemon and dies with the interpreter —
but `server_close()` at `shell.py:92` is also skipped (cosmetic, same reason). Suggest wrapping
`webview.start()` (or catching `Exception` from `build_shell` in the CLI dispatch) to emit one
line naming the `kimcad web` browser fallback, mirroring the pywebview-absent message.

### SHELL-004 — Minor — Docstring claims `open_external` is "wired as the js_api"; it is not wired to anything
`src/kimcad/shell.py:13` says the external-link bridge is "wired as the js_api so the SPA can
ask politely," but `create_window(...)` (`:74-80`) passes no `js_api=` and nothing else
references `open_external` — it is tested, documented, dead code. Today the SPA has no external
links (no `window.open`/`target="_blank"`/`ollama.com` in `kimcad.js`), so nothing escapes the
window either way, but Slice 11.6's Ollama detect-and-guide will need exactly this bridge.
Either pass `js_api` now or fix the docstring to say "ready to be wired."

### SHELL-005 — Minor — WebView2 profile lands in `%APPDATA%\pywebview`: writable (no installer break) but violates the plan's write-location lock — flag for Slice 11.4
Verified in installed pywebview 6.2.1 (`platforms/winforms.py:init_storage`): with
`private_mode=False` and no `storage_path`, the profile goes to `%APPDATA%\pywebview`. Good
news for the prompt's worry: never Program Files, nothing breaks under the installer. But the
plan's lock is "all writes go to `%LOCALAPPDATA%\KimCad`" (plan line 15) — this profile is (a)
outside that root, (b) **shared with any other pywebview app on the box** (cookies/localStorage
commingled in one browser profile), and (c) invisible to the 11.6 uninstaller sweep. Fix when
the 11.4 paths seam lands: `webview.start(..., storage_path=str(paths.data_dir() / "webview"))`.

### SHELL-006 — Minor — `shell.py` hardcodes the relative `output/web` root and is missing from Slice 11.4's modify list
`src/kimcad/shell.py:66` duplicates `Path("output") / "web"` (CWD-relative — under the
installer's shortcut the CWD may be the install dir, i.e. Program Files) instead of sharing
`webapp.serve`'s default. The plan's Slice 11.4 modify list names `webapp.py (output/web)` but
**not** `shell.py`, so the seam migration has a concrete miss waiting. Either route the shell
through a shared default now, or add `shell.py` to 11.4's file list.

### SHELL-007 — Nit — Vacuous assertion in `test_window_close_stops_the_server`
`tests/test_shell.py:83,93`: `serve_thread_alive = threading.Event()` is created and asserted
`not ...is_set()` but nothing ever sets it — the assertion can never fail (vestigial scaffolding
from the comment's intent). The test's real proof (post-shutdown `urlopen` raises `OSError`) is
sound — `URLError` subclasses `OSError`, and the socket is genuinely closed. Delete the Event
or make the serve thread set it. Note also the test calls `server_close()` itself, so the
production `start_gui=True` close ordering is only exercised by the GUI test — where it
produces SHELL-002's warning.

### SHELL-008 — Nit — `open_external` scheme check is case-sensitive (false negative, not a hole)
`src/kimcad/shell.py:41`: `startswith(("http://", "https://"))` quietly refuses
`HTTPS://ollama.com` — schemes are case-insensitive (RFC 3986 §3.1), so a legitimate link is
dropped. The security direction is correct (default-deny: leading whitespace, `javascript:`,
`javascript%3A`, `file:`, non-str all refused; tests cover it). Robust form: parse with
`urllib.parse.urlsplit(url.strip())` and allowlist `scheme.lower() in {"http", "https"}`.

### SHELL-009 — Nit — Ctrl+C in a console-launched shell is dead air, then (sometimes) a traceback
`webview.start()` blocks the main thread inside the .NET message loop; CPython only delivers
KeyboardInterrupt between bytecodes on the main thread, so Ctrl+C does nothing until the window
is closed by mouse — and a queued interrupt can then raise right at `shell.py:92` and escape
`main()` (which, unlike `webapp.serve`, has no KeyboardInterrupt handling) as a traceback.
Cosmetic: the installer path launches via shortcut, not a console. A `try/except
KeyboardInterrupt: pass` around the start/close pair would tidy the dev path.

## Questions the audit was asked, answered (no finding warranted)

- **Loopback bind:** the host is the literal `"127.0.0.1"`; port 0 only randomizes the port,
  never the interface — no path to a non-loopback bind. Same `_ExclusiveBindServer` as
  `kimcad web` (exclusive bind on Windows), and an ephemeral-port bind cannot collide, so the
  QA-006 port-in-use wrapper being absent here is correct, not missing.
- **Double shutdown:** safe. After `serve_forever` exits, `__is_shut_down` stays set, so the
  second `shutdown()` (closed handler then test/`server_close` path) returns immediately.
- **FakeEvents property/setter/`__iadd__` dance:** faithful. `events.closed += h` evaluates the
  getter, calls `__iadd__` (which appends and returns self), then the setter assigns the result
  back — exactly the semantics of pywebview's real `Event.__iadd__` returning itself.
- **Malformed config through the shell path:** `build_shell` calls `Config.load()` inside
  main's `try`, so `UnknownConfigKey`-family errors (RuntimeError subclass) get the friendly
  line. Raw YAML syntax errors (`yaml.ScannerError`) traceback — but identically so through
  `kimcad web` and `kimcad design` today; pre-existing posture, not a 11.1 regression.
  (Side note: `Config.load()` runs twice per shell launch — once in `build_shell`, once in
  `build_web_pipeline` — mirroring `serve()`'s existing double-load; harmless.)
- **`_normalize_argv` with bare `shell`:** `"shell"` was added to `_SUBCOMMANDS`, so it
  dispatches as a subcommand, never as a one-word design prompt; near-miss typos (`shel`) fall
  to argparse's choices error via the existing close-match guard. Covered by the passing
  `test_cli` suite.
- **Pins:** lock matches `pip freeze` exactly; pycparser 3.0 is the genuine current PyPI
  release (cffi 2.0's companion), not a 2.x typo; the pyproject win32 marker is valid PEP 508.

## Escalation verdict

**No escalation to audit-team.** The slice is small, the wiring and security posture are
fundamentally sound, and 8 of 9 findings are one-to-five-line fixes. But per the
zero-at-all-levels rule, **SHELL-001 (Major) must be resolved before Slice 11.1 is accepted**:
as written, the windowed app re-runs the first-run wizard on every launch and loses all
client-side UI state between runs — the one behavior `private_mode=False` was added to
guarantee. One launch of live verification could not have caught it; launch the shell twice
after fixing.
