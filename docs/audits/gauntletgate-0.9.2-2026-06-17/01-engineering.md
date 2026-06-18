# GauntletGate Full — Principal Engineer — KimCad 0.9.2

**Role:** Principal Engineer
**Audit date:** 2026-06-17
**Commit audited:** e91b148 (version sweep) on top of 9ddea46 (bug fixes)
**Severity roll-up:** Blocker 0 · Critical 0 · Major 1 · Minor 2 · Nit 2

---

## Findings

### ENG-001 · Major · Security / Architecture — `_child_env()` uses a weaker deny-list than the established `subprocess_env` module

**File:line:** `src/kimcad/ollama_runtime.py:140,145`

**Observed:**
```python
_SECRETISH = ("API_KEY", "APIKEY", "SECRET", "TOKEN", "PASSWORD", "_KEY", "CREDENTIAL")

run_env = {k: v for k, v in base.items() if not any(s in k.upper() for s in _SECRETISH)}
```

**Expected:**  
The project already has a canonical secret-scrub in `src/kimcad/subprocess_env.py` (`_SECRET_ENV_SEGMENTS` + `is_secret_env()`). That module strips `AUTH`, `PASSPHRASE`, `PASSWD`, `CREDENTIALS`, `PRIVATEKEY`, and applies whole-name-segment matching (so `TOKENIZER_PATH` survives while `SOME_TOKEN` is stripped). `_child_env()` rolls its own substring match against a different, shorter list — the two implementations have diverged.

**Gaps introduced by the mismatch:**

| Var pattern | `subprocess_env` | `_child_env()` |
|---|---|---|
| `GITHUB_TOKEN` | stripped (`TOKEN` segment) | **INHERITED** (only matches if `TOKEN` appears as substring; `GITHUB_TOKEN` → `.upper()` = `GITHUB_TOKEN` → `"TOKEN" in "GITHUB_TOKEN"` → ✓ actually caught) |
| `SSH_AUTH_SOCK` / `NPM_CONFIG__AUTH` | stripped (`AUTH` segment) | **INHERITED** — `"AUTH"` is not in `_SECRETISH` |
| `GIT_PASSPHRASE` / `GPG_PASSPHRASE` | stripped (`PASSPHRASE` segment) | **INHERITED** |
| `DB_PASSWD` | stripped (`PASSWD` segment) | **INHERITED** |

The Ollama child is a geometry runtime (it serves local model inference) — it has no legitimate use for SSH agent sockets, GPG passphrases, or npm auth tokens. These can be exfiltrated if the managed Ollama is ever compromised.

**Blast radius:** Medium. The managed Ollama binary is fetched from ollama.com (MIT license, embedded-use build) and runs on loopback only — the risk is lower than for an internet-facing process. But the pattern is wrong: OpenSCAD and CadQuery children already use the canonical scrub, and this process has MORE power than those (it runs a full inference server). The inconsistency means the deny-list can drift further without a test catching it.

**Fix path:** Replace `_SECRETISH` and the inline filter with `from kimcad.subprocess_env import is_secret_env` and `{k: v for k, v in base.items() if not is_secret_env(k)}`. Add `run_env.setdefault("OLLAMA_HOST", host)` and `run_env["OLLAMA_MODELS"] = ...` after (same as now). Delete the `_SECRETISH` constant. Add a test that `_child_env({}, ort.DEFAULT_HOST)` does not contain any key for which `subprocess_env.is_secret_env()` returns True.

---

### ENG-002 · Minor · Architecture — `_free_gb_on_receiving_drive()` reads `OLLAMA_MODELS` from the PARENT env, not from the child that will actually use the path

**File:line:** `src/kimcad/model_pull.py:75`

**Observed:**
```python
models_dir = os.environ.get("OLLAMA_MODELS") or (probe_dir or Path.home())
```

**Context:** `_child_env()` in `ollama_runtime.py` sets `OLLAMA_MODELS` as an env var in the **child** process's environment, not in the parent. The parent's `os.environ` only contains `OLLAMA_MODELS` if the user already had it set externally. When the managed Ollama is KimCad's own portable copy (the common cold-start case), `os.environ["OLLAMA_MODELS"]` is NOT set in the parent process, so `_free_gb_on_receiving_drive()` falls back to `probe_dir or Path.home()` instead of measuring the drive where the child will actually write.

**Impact:** The disk pre-check measures the wrong drive. If the user has `%LOCALAPPDATA%` on a separate SSD from their home directory, the check passes (home has space) but the download fills the LOCALAPPDATA drive. Conversely it could false-block a pull on a machine where home is small but LOCALAPPDATA is large. The error is bounded (the check is conservative and only an advisory estimate), but it's semantically wrong.

**Fix path:** In `_free_gb_on_receiving_drive()`, replace `os.environ.get("OLLAMA_MODELS")` with a direct call to `writable_root() / "models"` when in managed mode, or pass the computed path as `probe_dir` from the call sites that know they're about to start a managed Ollama.

---

### ENG-003 · Minor · Correctness — `cli.py` error handler emits "Start Ollama" + `ollama pull` in the error-recovery line immediately after printing `MODEL_UNAVAILABLE_MESSAGE`

**File:line:** `src/kimcad/cli.py:634-637`

**Observed:**
```python
print(f"Error: {MODEL_UNAVAILABLE_MESSAGE}", file=sys.stderr)
print(
    f"  Start Ollama, pull the model if you haven't (`ollama pull {_model_name()}`), "
    "then try again. `kimcad models` shows what's installed.",
    file=sys.stderr,
)
```

**Impact:** `MODEL_UNAVAILABLE_MESSAGE` now says "the engine isn't running" (no "Ollama" brand). But the recovery line immediately below it says "Start Ollama" and gives a raw `ollama pull` command. A user who has KimCad's managed Ollama (not a system install) will have no `ollama` CLI on their PATH, so this command doesn't exist for them. Additionally the fix's stated goal was to remove the Ollama brand from user-visible error paths — this is a CLI-visible user path that was missed.

**Blast radius:** CLI-only. The GUI path (webapp.py) is clean — it maps the error to the Settings-restart CTA with no CLI advice. This affects `kimcad design ...` users.

**Fix path:** Change the recovery line to either (a) route to the managed-engine vocabulary ("Restart the engine from Settings or `kimcad serve` on the command line"), or (b) keep the `ollama pull` hint but guard it with a `resolve_ollama_exe()` check — only print if a system Ollama is present. Short term: remove the "Start Ollama" reference and replace with "Run `kimcad serve` to start the engine" or similar.

---

### ENG-004 · Nit · Comment hygiene — Developer comment in pipeline.py still uses "Ollama" twice

**File:line:** `src/kimcad/pipeline.py:179,209`

**Observed:**
```python
# Stage 8.5 Slice 9: the local AI server (Ollama) couldn't be reached.
...
def _is_model_unreachable(e: BaseException) -> bool:
    """True if ``e`` is a model-server connection/timeout (Ollama down).
```

**Impact:** Not user-visible. These are internal dev comments, not surfaced in any API response or UI string. The 0.9.2 fix's stated scope was user-visible strings; internal comments correctly documenting implementation detail ("this catches the Ollama SDK's error type") are out of scope. Recording as Nit for completeness.

**Fix path:** No action required; or update wording on the next natural pass.

---

### ENG-005 · Nit · `VisionModelMissing` error message contains a raw `ollama pull` command

**File:line:** `src/kimcad/llm_provider.py:65-66`

**Observed:**
```python
"KimCad's image-reading model isn't downloaded yet. In a terminal, run: "
f"ollama pull {model} — then try again."
```

**Impact:** This string is sent to the browser as `body["error"]` when the vision model isn't installed (webapp.py:1991, 2033). Unlike the design-endpoint error, the vision endpoints return `model_unavailable` with this string as the error body — so "ollama pull" is visible in the UI on a cold-start machine. KimCad now manages Ollama, so users who went through the wizard won't have a bare `ollama` CLI. The terminal instruction is also in tension with the in-app "one-click setup" promise.

**Fix path:** Replace with a UI-appropriate recovery CTA: "KimCad's image-reading model isn't downloaded yet. Use Settings > AI setup to download it." This is a pre-existing issue not introduced in 0.9.2, but the 0.9.2 fix's vocabulary contract makes it a candidate for the same pass.

---

## What's working (specific and credited)

**Fix 1 — `MODEL_UNAVAILABLE_MESSAGE` placement and data flow: correct.**
The constant is defined once at `pipeline.py:202-205` and imported in three places (webapp.py:1988, 2030, 2111; cli.py:623). Every consumer that catches `_is_model_unreachable()` uses it. The web layer returns it verbatim as `{"status": "model_unavailable", "error": MODEL_UNAVAILABLE_MESSAGE}`. The frontend `designStatus.ts:75-82` picks up `result.error` directly — the string reaches the user exactly as written. No truncation, no wrapping, no transformation.

**The "Ollama" brand is correctly absent from the string itself.** The phrase "engine isn't running" is unique vocabulary. Three tests in test_webapp.py assert `"engine" in body["error"]`; the designStatus.test.ts fixture also uses the string `"the engine isn't running"`. Coverage is complete.

**Fix 2 — `OLLAMA_MODELS` pin: semantically correct for the stated goal.**
`_child_env()` at line 150 sets `run_env["OLLAMA_MODELS"] = str(writable_root() / "models")`. In installed mode, `writable_root()` is `%LOCALAPPDATA%\KimCad`, so the path is `%LOCALAPPDATA%\KimCad\models` — exactly the uninstaller's scope, solving the orphan-after-uninstall problem. In dev mode, `writable_root()` returns the repo root (correct for local development). The `start_serve()` function is the single entry point from which `_child_env()` is called; `ensure_serving()` → `start_serve(exe)` is the only call chain. The test at test_ollama_runtime.py:96-99 verifies the value using the same `writable_root()` call, so it will track correctly across install modes.

**`_is_model_unreachable()` coverage is thorough.** The three exception classes it checks (`APIConnectionError`/`APITimeoutError` for the OpenAI-SDK path; `urllib.error.URLError` for the native path; `TimeoutError`/`ConnectionRefusedError`/`ConnectionResetError` for OS-level errors) cover every realistic Ollama-down signal. The duck-typed class-name check for the OpenAI SDK class avoids an import dependency. Test coverage exercises all three paths.

**Version consistency is complete.** pyproject.toml, frontend/package.json, CHANGELOG.md, README.md, docs/install-guide.md all read 0.9.2. The single-source test (`test_version_single_source.py`) ensures no copy drifts.

**`_child_env()` is the only spawn path for the managed Ollama.** `ensure_serving()` → `start_serve(exe)` is the only chain; `model_pull._run_setup()` calls `serve(exe)` which defaults to `_ort.start_serve(e)`. No orphan spawn sites.

**The DENY-list's existing entries are correct for the cases they cover.** `API_KEY`, `APIKEY`, `SECRET`, `TOKEN`, `PASSWORD`, `_KEY`, `CREDENTIAL` as substrings of the uppercased key name will catch the common cloud credential patterns (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_KEY`). The gap is only for the entries in `subprocess_env.py` that `_SECRETISH` lacks.

---

## Coverage gaps / what couldn't be assessed

**Live installed-mode behavior of `writable_root() / "models"` path:** The audit environment is dev mode (`KIMCAD_INSTALL_ROOT` unset), so `writable_root()` returns the repo root, not `%LOCALAPPDATA%\KimCad`. The installed-mode path can only be verified on a machine running the installed build. The code path is correct by inspection; the tester's clean-machine run is the live coverage source.

**`VisionModelMissing` / vision-error `model_unavailable` paths:** The vision error paths in webapp.py return `model_unavailable` with the `VisionModelMissing` exception string (`"ollama pull ..."`) or a `VisionReadError` HTTP code — neither is `MODEL_UNAVAILABLE_MESSAGE`. This is pre-existing and not a 0.9.2 regression, but it means `"engine" in body["error"]` is NOT true for the `VisionModelMissing` path. test_webapp.py line 1437-1438 asserts it for the `_is_model_unreachable` branch specifically, so the test is accurate, not over-claiming. The `VisionModelMissing` path is a separate status code path and correct by its own contract.

**`model_pull._free_gb_on_receiving_drive()` integration test:** No test verifies the disk-space check measures the correct path when `OLLAMA_MODELS` is not set in the parent env but is set in the child. The unit tests likely mock `os.environ`.
