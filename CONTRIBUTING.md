# Contributing to KimCad

Thanks for your interest. KimCad is open source (Apache-2.0) and welcomes bug reports,
ideas, and pull requests.

## Ways to help

- **Found a bug?** Open an [issue](../../issues) with exact reproduction steps. If it's a
  design that came out wrong, include the prompt and the `output/` report.
- **Have an idea or a question?** Start a [Discussion](../../discussions) — that's the right
  home for "could KimCad do X?" and "how do I…?".
- **Ran KimCad against a real printer?** That's the most valuable report right now (see the
  status note below). Post it in Discussions with the printer, the connection type, and what
  happened.
- **Want to send code?** Read on.

## The build & test gate

KimCad has one authoritative gate, `scripts/ci.sh`, run by the pre-push hook **and** by the
self-hosted CI runner — the same script in both places, so "passes locally" means "passes
CI." It runs:

- `ruff` (lint),
- the full `pytest` suite, including the **live OrcaSlicer slice** and the CadQuery worker
  sandbox tests,
- the frontend **Vitest** suite,
- a committed-SPA **build-reproducibility** check (the built UI is committed; it must match a
  fresh build),
- the **installer-staging smoke** (`build_installer --stage-only` + `verify_install`),
- a **binary advisory review** (`scripts/check_binary_advisories.py` — every pinned
  OpenSCAD/OrcaSlicer version must carry a reviewed CVE assessment; bumping a pin without
  one fails the gate; the bump process is in that script's docstring). The CI workflow
  additionally runs **pip-audit** against `requirements.lock` for the Python tree,
- and, in release mode, live-tool proof.

Enable the hook once per clone:

```
git config core.hooksPath .githooks
```

Every `git push` then runs the gate and blocks the push if anything fails.

### Test markers (running off the Windows target box)

The authoritative gate runs on the Windows target with the fetched binaries, so it runs
**everything**. If you develop on another OS or without the binaries, env-dependent tests
**skip cleanly** (they never hard-fail off their environment). Markers (declared in
`pyproject.toml`, auto-skipped by `tests/conftest.py`):

| Marker | Skipped when | Select a fast subset |
|---|---|---|
| `live` | — (run with the OrcaSlicer binary) | `pytest -m "not live"` |
| `real_tool` | the OpenSCAD/OrcaSlicer binary isn't fetched | `pytest -m "not real_tool"` |
| `windows_only` | not on Windows (e.g. exclusive socket bind) | `pytest -m "not windows_only"` |
| `needs_manifold` | `manifold3d` isn't installed | `pytest -m "not needs_manifold"` |
| `needs_cadquery` | no CadQuery interpreter is discoverable | `pytest -m "not needs_cadquery"` |
| `needs_browser` | Playwright Chromium isn't installed (`playwright install chromium`) | `pytest -m "not needs_browser"` |
| `browser_serial` | — (not an env gate; serializes the e2e tests around the one shared localhost server — inert under the default single-process runner, matters only under xdist) | not a `-m "not ..."` selector |

A fast cross-platform inner loop:
`pytest -m "not live and not real_tool and not windows_only"`. The gate on the target box
still asserts the live-tool contract executed with **zero skips** — markers give contributors
a clean signal, they do not weaken the gate.

### Fork pull requests (hosted smoke)

The self-hosted gate is **push + manual only** — a self-hosted runner must never execute
untrusted fork code. So fork PRs get a separate hosted check, `.github/workflows/pr-smoke.yml`
(KC-12): on a throwaway GitHub-hosted Ubuntu runner it runs **ruff + the hermetic `pytest`
subset** (`-m "not live"`; the binary/interpreter/Windows-only tests auto-skip there) **+ the
frontend vitest suite** — a fast green/red signal without exposing the self-hosted box. It does
**not** prove the live OpenSCAD/OrcaSlicer/CadQuery contract or byte-exact SPA build
reproducibility; a maintainer runs the full self-hosted gate on the branch before merge.

### Diff-coverage gate (KC-22)

Incoming PRs must keep **changed lines covered**: the PR smoke runs `pytest --cov=kimcad` and then
`scripts/check_diff_coverage.py`, which fails the PR if the lines this PR changes in `src/kimcad`
are **< 80% covered overall**, or if any single module with **≥ 20 changed lines** is **< 70%
covered**. Coverage is scoped to shipped library code (changed `tests/`, `scripts/`, and docs don't
count). Note the PR smoke measures the *hermetic* subset (live-tool tests are skipped there), so a
line reachable only by a live test reads as uncovered — keep diff-coverable logic unit-testable.

To self-check a branch before opening a PR (this self-hosted gate runs on push to `main`, where
there's nothing to diff, so it doesn't run diff-coverage itself):

```
.venv/Scripts/python -m pytest -q --cov=kimcad --cov-report=xml
.venv/Scripts/python scripts/check_diff_coverage.py coverage.xml --compare-branch origin/main
```

The threshold logic is unit-tested in `tests/test_check_diff_coverage.py`.

### End-to-end browser tests (KC-20)

`tests/e2e/` is a Playwright suite that drives the **real** KimCad SPA in a real headless Chromium
against a real `kimcad web --demo` server — no DOM mocks, no stubbed APIs. Demo mode stubs only the
*model* (the LLM→plan path), so the suite is deterministic without Ollama; but it still renders with
the real **OpenSCAD** binary (and the export journey slices with **OrcaSlicer**), so most journeys
need those binaries. Each test also asserts the browser console stayed clean (no errors / uncaught
exceptions), so it proves the SPA is *wired*, not just that the right text rendered. (The real model
path — LLM→plan and cloud routing — is deliberately **out of e2e scope**; it's covered by the
unit/benchmark suites.)

The browser tooling is **not** in `requirements.lock` (it's test-only and must never enter the
shipped installer); the gate pins it to the same versions `pip install -e ".[dev]"` resolves, so
local and CI match. To run the suite locally:

```
pip install -e ".[dev]"            # playwright + pytest-playwright, pinned to the gate's versions
playwright install chromium         # the browser binary (a pip lock can't express this)
python scripts/fetch_tools.py       # OpenSCAD + OrcaSlicer — most journeys render/slice with them
pytest tests/e2e -q
```

Where Chromium isn't installed (a fresh clone, the hosted fork-PR smoke), the suite **skips
cleanly** via the `needs_browser` marker; without the binaries, the design/on-ramp/export journeys
skip via `real_tool` (so only the smoke + wizard journeys run). The provisioned self-hosted gate has
both, so there the e2e tests run with no green-by-skip. The harness modules (smoke, wizard) carry
`pytestmark = [browser_serial, needs_browser]`; the design-triggering modules add `real_tool`.

### Regenerating `requirements.lock`

`requirements.lock` is the single pinned set the installer, CI, and the from-source path all consume
(`scripts/build_installer.py` installs it, then strips the dev/build toolchain via `RELEASE_STRIP_NAMES`
so only runtime deps ship). The policy is **batteries-included**: the lock pins the base runtime deps,
the gate's dev tooling, **and both** optional connector extras (`bambu` + `serial`) so the official
installer drives every supported printer — including a USB Marlin/Ender — out of the box, with no manual
`pip` step (ENG-001). To regenerate after a dependency change:

1. In a clean Python **3.13** venv: `pip install -e ".[dev,bambu,serial]"`.
2. Freeze, excluding the editable project itself and the Playwright browser tooling (test-only — it must
   never enter the installer, and a pip lock can't express its browser binary anyway):

   ```
   pip freeze --exclude-editable | grep -viE '^(playwright|pytest-playwright)==' > requirements.lock
   ```

3. Re-run the gate: `tests/test_build_installer.py` asserts every runtime dep **and** both connector
   extras are in the lock, and CI's `pip-audit -r requirements.lock` must stay clean.

## Setup for development

From-source setup is in the [README's Setup section](README.md#setup): a Python **3.13**
venv, `pip install -e ".[dev]"`, then `python scripts/fetch_tools.py` for the OpenSCAD /
OrcaSlicer binaries. The frontend needs Node only to *rebuild* the UI
(`npm --prefix frontend ci && npm --prefix frontend run build`); the committed build is
what ships.

## House style

- **Tests first.** The project is built test-driven; a change that touches behavior comes
  with a test that would fail without it.
- **Match the surrounding code** — its naming, comment density, and idioms. Comments explain
  *why*, and reference the finding/decision they implement where one exists.
- **Honesty in copy and docs.** KimCad never narrates a simulated action as a real one,
  never claims a check ran when it didn't, and keeps "validated against a mock" distinct from
  "validated on hardware." Keep it that way.
- **Keep the gate green.** Don't disable a check to get a change through; fix the cause.

## A note on scope (the beta)

Real-printer validation happens on the maintainer's hardware during the beta. Connectors are
**API-validated** against runnable mocks but not yet **metal-validated** — see
[supported-printers.md](docs/supported-printers.md) and
[first-hardware-contact.md](docs/beta/first-hardware-contact.md). PRs that touch the
hardware-send path are very welcome, but will be merged conservatively and verified against
the mocks until they can be checked on a real machine.

## License

By contributing, you agree your contributions are licensed under the project's
[Apache-2.0](LICENSE) license.
