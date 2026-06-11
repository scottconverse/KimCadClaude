# Audit Lite — Stage 11 Slice 11.3 (version normalization, commit 7481f55)
**Date:** 2026-06-10
**Scope:** Commit 7481f55 only — `0.9.0b1` single-sourced from package metadata: `kimcad.__version__` via `importlib.metadata`, CLI `--version`, MCP `serverInfo`, `/api/health`, frontend `package.json` bump, tripwire test `tests/test_version_single_source.py`, plus the diagnostic-richer concurrent-saves assert.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship. The single-source mechanism is correct on every surface checked, the one real risk
(does `importlib.metadata` find the dist-info in the Slice 11.5 `pip install --target`
INSTALLED layout?) was **verified empirically and clears**, and the commit's verification
claims check out against the commit's exact contents. Two Minors: the frontend
`package-lock.json` was left at `0.1.0`, and the tripwire has named blind spots
(`package*.json` now, `installer/*.iss` later).

> **Note on environment:** mid-audit, uncommitted Slice 11.4 work appeared in the working
> tree (`cli.py`, `config.py`, `shell.py`, `webapp.py`). All commit-level verification below
> was re-run against a clean `git archive 7481f55` extraction to keep the audit honest.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 2
- Nit: 0

## Findings

### FINDING-001 Minor: `frontend/package-lock.json` still says `0.1.0` — lockstep claim is incomplete
**Dimension:** Correctness
**Evidence:** `frontend/package-lock.json:3` and `:9` — root `"version": "0.1.0"` (both the
top-level field and the `""` package entry). `frontend/package.json` was bumped to
`0.9.0-beta.1` but the lock was not regenerated.
**Why it matters:** The commit message claims the frontend is "in lockstep"; the lock file
isn't. The next `npm install` will silently rewrite the lock's root version, producing an
unexplained dirty diff in someone else's commit. The tripwire can't catch it: it sweeps
`frontend/src/**/*.ts*` only, and the lock carries the npm-semver form anyway.
**Fix path:** Run `npm install --package-lock-only` (or plain `npm install`) in `frontend/`
and commit the lock alongside the next slice.

### FINDING-002 Minor: tripwire blind spots — `package*.json` today, `installer/*.iss` at Slice 11.5
**Dimension:** Tests
**Evidence:** `tests/test_version_single_source.py:34` — the sweep covers exactly two trees:
`src/kimcad/*.py` and `frontend/src/*.ts*`. Not swept: `frontend/package.json` /
`package-lock.json` (so the `0.9.0b1` ↔ `0.9.0-beta.1` lockstep is enforced by hand, not by
test — FINDING-001 is the proof it can drift), `scripts/`, and the future `installer/` tree.
The plan's intent is on record (`pyproject.toml:7-9`: "the installer's filename + wizard"
read the version from metadata; "no other file may carry a literal copy") — but when the
`.iss` lands, Inno Setup cannot import Python metadata, so the natural move is a literal
`#define MyAppVersion "0.9.0b1"`, which this tripwire will not see.
**Why it matters:** The single-source guarantee is only as wide as the sweep. The first
version bump after the installer exists is exactly when a stale literal in the `.iss` ships
a mislabeled installer.
**Fix path:** At Slice 11.5, either (a) generate the `.iss` version line from `pyproject.toml`
in the build script and add `installer/` + `frontend/package.json` to the tripwire's sweep
(asserting the `b1` ↔ `-beta.1` mapping for the latter), or (b) pass
`/DMyAppVersion=$(python -c "...")` on the `iscc` command line so no literal ever exists.
Either keeps the pyproject comment's promise true.

## Hunt results (the five directed checks)

1. **Editable-install staleness / `--target` INSTALLED layout — VERIFIED, clears.**
   - Probe: `pip install --target %TEMP%\kimcad-target-probe --no-deps <commit snapshot>`
     produced `kimcad/` **and** `kimcad-0.9.0b1.dist-info/` in the target.
   - `PYTHONPATH=<target>` then `py -3.13 -c "import kimcad; print(kimcad.__version__)"`
     (a non-venv interpreter, so no site-packages fallback) → `0.9.0b1`, module loaded from
     the staging dir. `importlib.metadata` resolves dist-infos from `sys.path`, so the
     Slice 11.5 layout works as-is. The dev-tree staleness story is also sound: the test's
     assert message names the exact remedy (`pip install -e . --no-deps`), and an uninstalled
     tree degrades to the visibly-fake `0.0.0.dev0`, never a plausible release string.
2. **Tripwire blind spots** — real but bounded; see FINDING-002. Docs are excluded by
   design and that's fine (CHANGELOG legitimately names versions).
3. **CLI `--version` vs required subparser — VERIFIED, clears.** Live run:
   `python -m kimcad.cli --version` → `kimcad 0.9.0b1`, exit 0 (argparse's `version` action
   prints and exits before the required-subcommand check fires); bare `python -m kimcad.cli`
   → usage + "the following arguments are required: command", exit 2. Both correct.
4. **PEP 440 vs npm semver (`0.9.0b1` vs `0.9.0-beta.1`) — no consumer compares them.**
   The frontend treats the version as an opaque string from `/api/health`
   (`frontend/src/api.ts:374`; SettingsPanel renders `v{version}`); nothing reads
   `package.json`'s version at runtime (no `import.meta.env`/version import anywhere in
   `frontend/src`). The two strings never meet. The only lockstep risk is drift, covered by
   FINDING-001/002.
5. **MCP `serverInfo` — no stale assertion.** `tests/test_mcp_server.py:40` asserts only the
   server *name*; no test anywhere asserts `"0.1.0"` (repo-wide grep: remaining `0.1.0` hits
   are `package-lock.json` (FINDING-001), the tripwire's own pattern, an unrelated
   `proxy-tools==0.1.0` pin, and historical audit records).

## Verification run (real results)

| Check | Result |
|---|---|
| `pytest tests/test_version_single_source.py tests/test_mcp_server.py tests/test_cli.py -q` (live tree) | **54 passed**, 4.46s |
| Same three files against the clean commit extraction (`git archive 7481f55`, `PYTHONPATH` to snapshot src) | 53 passed, 1 failed — `test_design_slice_flag_confirms_and_reports`, an **environmental** failure: the snapshot lacks the repo-local `tools/orcaslicer` install the test depends on. Pre-existing trait, not introduced by this commit; passes in-repo. See watch item. |
| `ruff check` (clean commit extraction) | **All checks passed** — the commit's "ruff clean" claim is true. (The live tree currently fails F401 `os` unused in `shell.py:24` — that's from *uncommitted* Slice 11.4 work, out of scope.) |
| `pip install --target` + non-venv import probe | `0.9.0b1` from staging dist-info (hunt item 1) |
| `kimcad --version` / bare invocation | exit 0 / exit 2 + usage (hunt item 3) |

## What's working
- **The single-source mechanism is genuinely single.** One literal in `pyproject.toml`; all
  four runtime surfaces (`__init__.py`, `cli.py:60`, `mcp_server.py:31-37` lazy
  `_app_version()`, `webapp.py:1165-1176` `_handle_health`) read the attribute. The lazy MCP
  read degrading at call time rather than import time is a thoughtful touch.
- **The tripwire is a real tripwire within its sweep** — it pins metadata==pyproject, bans
  both the declared version and the old `0.1.0` literal from `src` + `frontend/src`, and
  exercises CLI and `/api/health` live. Test mocks moved to the obviously-fake `9.9.9-test`
  is exactly right.
- **The concurrent-saves assert upgrade** (`tests/test_connections_api.py:177-182`) does what
  it says: the next flake will name the failing request and body instead of a bare
  `assert 200`.

## Watch items
- **Clean-machine pytest** (relevant to Stage 11's clean-VM definition of done):
  `test_cli.py::test_design_slice_flag_confirms_and_reports` silently depends on
  `tools/orcaslicer` existing under the repo root — it fails on a bare checkout. Expect it
  (and any siblings) at the Slice 11.5/11.6 clean-VM gate.
- **Uncommitted 11.4 work in flight** has a live `ruff` F401 (`shell.py:24`, `os` now unused)
  — catch it before the 11.4 commit claims "ruff clean".
- **Dual dist-info ambiguity:** if a future packaged layout ever puts both a venv
  site-packages and the `--target` staging dir on `sys.path`, whichever is first wins the
  metadata lookup. Keep the installed layout single-pathed (it currently is).

## Escalation recommendation
No escalation needed. Zero Blocker/Critical/Major; both Minors are one-command or
one-slice-ahead fixes, and the one directed risk worth a full investigation (the `--target`
metadata lookup) was probed empirically and clears.
