# Stage 11 Beta Gate — Principal Engineer + Test Engineer deep-dive

Date: 2026-06-10 · HEAD: 7f8b0d3 · Scope: the Stage 11 diff (07fb3ad..HEAD) and the real
installed artifact at `%TEMP%\kimcad-install-test` (silent-installed from
`dist/KimCad-Setup-0.9.0b1.exe`). Prior per-slice audit-lites (11.1–11.5) read; remediated
items spot-verified, not re-reported.

## Severity rollup

| Blocker | Critical | Major | Minor | Nit | Info |
|--------:|---------:|------:|------:|----:|-----:|
| 0 | 0 | 1 | 4 | 2 | 1 |

## What was actually run / probed (evidence)

- `.venv\Scripts\python.exe -m pytest tests/test_build_installer.py tests/test_paths.py
  tests/test_shell.py tests/test_version_single_source.py -q` → **21 passed in 8.11s**.
- Installed tree: `python\python.exe kimcad_launcher.py --version` → `kimcad 0.9.0b1` (green).
- Installed tree import surface on the EMBEDDED interpreter:
  `import kimcad.webapp, kimcad.connectors, kimcad.config, kimcad.shell, kimcad.cli,
  kimcad.mcp_server` → **green** (no stripped package needed at import).
- Installed tree contents enumerated (95 top-level entries in `site-packages`); grepped for
  `pkg_resources` / `setuptools` / `tkinter` importers; `python313._pth` read (stock:
  `python313.zip`, `.`, `#import site` — as documented).
- `import py` on the embedded interpreter → `ModuleNotFoundError: No module named '_pytest'`
  (see BG-E002).

## Spot-verified prior remediations (all hold)

- **11.5 FINDING-001 (release strip):** pytest/_pytest/pluggy/iniconfig/pip/wheel/pygments/
  coverage/ruff are absent from the installed `site-packages` — the strip is real (one
  leftover found, BG-E002).
- **11.5 FINDING-003 (verify scope):** `scripts/verify_install.py` now snapshots the ENTIRE
  app tree via `rglob` before/after and fails on any new path — the claim matches the check.
- **11.4 FINDING-001/-002 (seam bypasses):** `cadquery_runner.py` imports `PROJECT_ROOT` from
  `kimcad.config` (line 66) and `llm_provider.py`'s `LIBRARY_DIR` derives from the same
  routed root (lines 43–45). Routed, with the audit IDs cited in comments.
- **11.3 FINDING-001 (lockstep):** `frontend/package-lock.json` now carries `0.9.0-beta.1`
  in both version fields.

## Findings

### BG-E001 — Major (test) — nothing automated ever builds or verifies the installer pipeline; the beta artifact's whole proof chain is manual

`.github/workflows/ci.yml` + `scripts/ci.sh` run ruff, the full pytest suite, the live
subset, vitest, SPA repro, and pip-audit — but **no step stages `dist/staging`, runs
`smoke_staging`, exercises the strip assertion, or runs `verify_install.py`**.
`tests/test_build_installer.py` is static-only (regex/AST over source text). Consequently a
whole class of regressions breaks ONLY the installed artifact while CI stays green:

- a runtime dep added to `pyproject.toml` but not `requirements.lock` (kimcad is staged with
  `--no-deps`; the lock-consistency net is two spot pins — BG-E007);
- a strip-list edit that over-reaches into a runtime package (the assertion only fires for
  under-strips);
- `sys.path.insert` moved after the kimcad import in the launcher (BG-E005);
- embeddable-pin rot vs the dev venv.

Today every one of those is caught only when a human next runs `scripts/build_installer.py`.
**Judgement asked for:** `test_build_installer.py` does NOT suffice as the beta gate's trust
anchor. Owed: a release-gated CI step (the existing `KIMCAD_RELEASE=1` lever fits) that runs
`build_installer.py --stage-only` (network: the pinned embeddable zip + PP3D, both cached)
followed by `verify_install.py dist/staging`. That executes the strip assertion, the
embedded-interpreter smoke, AND the five install contracts on every release run.

### BG-E002 — Minor (eng) — pytest's `py.py` shim ships in the release, and it's broken

`%TEMP%\kimcad-install-test\site-packages\py.py` is pytest's pylib compatibility shim
(`import _pytest._py.error …`). The strip globs (`pytest*`, `_pytest*`, `py.test*`) and the
leftover assertion all miss it, so it shipped — and since `_pytest` was stripped, it raises
`ModuleNotFoundError` on import (confirmed on the embedded interpreter). Nothing in the
shipped tree imports `py` (grepped), so impact is a dead module + proof the glob-based
strip/assert has blind spots for non-prefix artifacts. Fix: add `py.py` to `RELEASE_STRIP`
(exact name), or strip by consulting the stripped dists' `RECORD` files instead of globs.

### BG-E003 — Minor (eng) — setuptools 82.0.1 (8.5 MB, including its own test suite) rides in the release payload

`requirements.lock` pins `setuptools==82.0.1`, it is not in `RELEASE_STRIP`, so the
installed artifact carries `setuptools/` (8.5 MB — `setuptools/tests/**` included),
`_distutils_hack/`, and `distutils-precedence.pth`. Verified: no shipped package imports
`pkg_resources` at runtime (setuptools 82 dropped it; it isn't even present), `cffi`'s
setuptools imports are build-time-only modules, and the core kimcad import surface is green
without it. Same finding class as the remediated 11.5 FINDING-001, smaller scale. The
`.pth` is inert because the embeddable python never runs `site` — worth a build-script
comment that .pth-dependent packages can never work in this layout. Fix: add
`setuptools`, `_distutils_hack`, `distutils-precedence.pth` to the strip, rebuild, re-run
verify (the existing cycle).

### BG-E004 — Minor (test) — the artifact has never been exercised from a path with spaces, yet the DEFAULT install dir has one

The real install test ran at `%TEMP%\kimcad-install-test` (no spaces); the `.iss` default is
`{autopf}\KimCad` → `C:\Program Files\KimCad` (space; `Program Files (x86)` adds parens for
a 32-bit-PF edge). Code-read says safe: the `.iss` quotes the launcher path in `[Icons]` and
`[Run]` `Parameters` (and Inno auto-quotes `Filename`); the launcher derives everything from
`Path(__file__)`; `paths.py` is pathlib end-to-end; **zero `shell=True` anywhere in `src/`**
(grepped) so tool invocations pass argv lists. But "reasoned safe" is not "proven": neither
`smoke_staging` nor any verify run has executed the payload from a spaced/parenthesised
directory. Cheap closure: one verify (or a staging copy) under a temp dir named like
`kimcad gate (spaces)` — ideally folded into BG-E001's CI step.

### BG-E005 — Minor (test) — the launcher AST contract checks the env switch but not the sys.path ordering

`tests/test_build_installer.py::test_launcher_sets_the_seam_before_any_kimcad_import`:
mutation-checked — moving the `KIMCAD_INSTALL_ROOT` write after the import **does** fail the
test (the lineno comparison is computed correctly for the real mutation; it is conservative
for the env-write-after-`def main` layout, which fails the test despite being runtime-correct
— acceptable direction). Two gaps: (a) the docstring-stated contract is "env set AND
site-packages pathed" but only the env half is asserted — moving `sys.path.insert` into
`main()` below the import bricks the installed app with CI green (only the manual
`smoke_staging` catches it); (b) the env-line detector takes the FIRST `ast.walk` hit rather
than `min(lineno)` (walk order ≠ line order) — correct today with one occurrence, fragile the
day a second `KIMCAD_INSTALL_ROOT` reference appears. Fix: assert the insert's lineno too,
and take min() on both sides.

### BG-E006 — Nit (eng) — `scripts/ci.sh` header describes a hosted-CI world that no longer exists

The header says hosted GitHub Actions is "an intentionally PARTIAL smoke check (Python lint +
pytest only, Linux)". `ci.yml` has been the self-hosted Windows runner executing ci.sh itself
(plus the live-subset and pip-audit steps) since the Stage-A gate, and disposition #3 makes
self-hosted THE gate. Stale comment; one paragraph fix.

### BG-E007 — Nit (test) — lock-vs-pyproject consistency is two spot pins

`tests/test_project_hygiene.py` asserts only `numpy==2.2.6` and `scipy==1.17.1` are in the
lock. A new `[project] dependencies` entry missing from `requirements.lock` ships a broken
artifact (staging installs the lock, then kimcad `--no-deps`) and nothing fails until the
next manual build's smoke. Either parse pyproject deps and assert each name appears in the
lock, or accept BG-E001's CI staging step as the net.

### BG-E008 — Info — pip-audit posture of the SHIPPED set is sound; the unscanned surface is the binaries

The shipped `site-packages` is a strict subset of `requirements.lock` (enumerated and
matched) plus first-party kimcad, and CI runs `pip_audit -r requirements.lock --strict` — so
every shipped wheel is CVE-scanned (the lock's dev-only pins add noise, not gaps). What no
scanner covers: the pinned embeddable CPython 3.13.13, OpenSCAD, OrcaSlicer, and
PrintProof3D v0.5.0 binaries — staleness is policy-by-comment (accepted at 11.5 F-005).
Recorded for the watchlist, not actioned.

## Hunts that came back clean (negative results, with method)

- **Trailing backslash on `KIMCAD_INSTALL_ROOT`:** the `.iss` never sets env; the only writer
  is the launcher, via `str(Path(__file__).resolve().parent)` — pathlib never emits a
  trailing separator, and `paths.py` re-wraps in `Path()` which normalizes one anyway. An
  empty-string env reads as not-installed (falsy) — coherent. Non-issue.
- **tkinter:** the embeddable runtime ships no tcl/tk (verified); the only tkinter importers
  in the shipped tree (`PIL/ImageTk.py`, `PIL/_tkinter_finder.py`, `tqdm/tk.py`) are
  on-demand modules no kimcad path imports. Core import surface proven green on the embedded
  interpreter.
- **`pkg_resources`:** absent from the artifact (setuptools 82 dropped it) and no shipped
  module imports it at runtime.
- **Connections card vs read-only install:** card writes go to `~/.kimcad/settings.json`
  (`SettingsStore.update_connector`, whole read-merge-write under `_WRITE_LOCK`); the config
  overlay path is `%LOCALAPPDATA%\KimCad\config\local.yaml` via `paths.user_config_path()`;
  the installed `config/` ships `default.yaml` only (verified on the artifact). The
  full-tree diff in `verify_install` pins "install dir untouched". Overlay field whitelist +
  200-char cap + secrets-stay-in-env all hold per the remediated 11.2 audit.
- **Installed-mode relative-path overrides:** a user-set relative `paths.history`/
  `paths.designs` in local.yaml resolves against the read-only install root — but every such
  write is best-effort/degrading by design, the defaults are per-user, and it requires a
  hand-authored override; noted, not filed.

## Top 3

1. **BG-E001** — give the beta gate an automated leg to stand on: a release-gated CI step
   running `--stage-only` + `verify_install dist/staging` (also closes BG-E004/E005(a)/E007).
2. **BG-E003** — strip setuptools/_distutils_hack/the .pth from the payload (8.5 MB + a
   shipped third-party test suite in a release artifact).
3. **BG-E002** — fix the strip's blind spot (`py.py` ships broken) and harden the leftover
   assertion so the next blind spot can't recur silently.
