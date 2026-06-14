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
