#!/bin/sh
# Local CI gate — the AUTHORITATIVE pre-push gate (run on Windows): ruff + the full pytest
# suite (incl. the live OrcaSlicer slice) + frontend vitest + SPA build-reproducibility +
# release-mode live-tool proof. The SAME script is what the SELF-HOSTED GitHub Actions
# runner executes (.github/workflows/ci.yml — the full gate on this box since Stage A,
# plus the installer staging smoke; hosted runners are not used — owner decision, see
# docs/audits/stage-11/dispositions-2026-06-10.md). Used by the pre-push hook
# (.githooks/pre-push) and runnable by hand.
set -e
cd "$(git rev-parse --show-toplevel)"

if [ -x .venv/Scripts/ruff.exe ]; then
    RUFF=.venv/Scripts/ruff.exe
    PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/ruff ]; then
    RUFF=.venv/bin/ruff
    PY=.venv/bin/python
else
    RUFF=ruff
    PY=python
fi

echo "[ci] ruff check..."
"$RUFF" check src tests
# ENG-007: a missing/broken geometry backend degrades trimesh silently and makes ~30 tests fail with
# misleading "logic" errors. Fail the gate FAST and CLEARLY here so the authoritative push gate can
# never go green on a degraded environment (the pytest collection hook only SKIPS locally).
echo "[ci] geometry backends..."
"$PY" scripts/check_geometry_backends.py
# KC-5 (#10): the pinned binaries' curated CVE/advisory review (offline + deterministic;
# pip-audit in the CI workflow covers the Python tree). Fails on a blocking advisory OR a
# pin bumped without a review.
echo "[ci] binary advisories..."
"$PY" scripts/check_binary_advisories.py
# Gate-integrity 2026-06-13: the CadQuery worker's cold OCP/OCCT import is slow, and this old
# self-hosted runner thermal-throttles under a sustained full-gate load — the production-default
# 120 s render / 90 s discovery-probe timeouts then flake on the FIRST (cold) CadQuery render
# (box/tube exceeded 120 s on a 30-min throttled run). Grant the gate generous headroom; runtime,
# with these unset, keeps the tight production defaults. Hosted runners (#16) retire this box.
export KIMCAD_CQ_TIMEOUT_S="${KIMCAD_CQ_TIMEOUT_S:-360}"
export KIMCAD_CQ_PROBE_TIMEOUT_S="${KIMCAD_CQ_PROBE_TIMEOUT_S:-240}"
echo "[ci] pytest..."
# -ra surfaces skip reasons so a green run without the bundled OrcaSlicer binary can't be
# mistaken for one that proved the real slicer contract (TEST-002).
# TEST-001 (stage-BCD gate): on the fully-provisioned CI box, EVERY test must execute —
# a skip there means tools/profiles/interpreter drift hid real coverage (the binary-gated
# tests aren't `live`-marked, so the live-subset assertion alone can't see them). Local
# dev runs stay lenient (a fresh clone legitimately skips tool-gated tests).
PYTEST_OUT="$(mktemp)"
# Gate-integrity 2026-06-13: a bare `pytest | tee` reports tee's exit (always 0), so under POSIX sh
# (no pipefail — and the pre-push hook can invoke this with plain `sh`) a FAILING suite would sail
# through and the push go GREEN (this masked a real failure on 2026-06-13). Run pytest with NO pipe
# in the critical path — redirect output to a file and capture its real exit status via
# `|| PYTEST_RC=$?` (which also keeps `set -e` from aborting before we record it) — then print the
# output. Correct under sh and bash alike; no pipefail required.
PYTEST_RC=0
# --durations=15 surfaces the slowest tests so the e2e browser journeys' wall-clock on this
# thermally-throttling box is visible + bounded, not an invisible tax on the gate (KC-20 QA-3).
"$PY" -m pytest -q -ra --durations=15 >"$PYTEST_OUT" 2>&1 || PYTEST_RC=$?
cat "$PYTEST_OUT"
if [ "${KIMCAD_CI_STRICT:-}" = "1" ] && grep -qE '[0-9]+ skipped' "$PYTEST_OUT"; then
    echo "[ci] STRICT GATE: tests were SKIPPED on a provisioned runner — coverage silently lost:"
    grep -E '^SKIPPED' "$PYTEST_OUT" || true
    rm -f "$PYTEST_OUT"
    exit 1
fi
rm -f "$PYTEST_OUT"
if [ "$PYTEST_RC" -ne 0 ]; then
    echo "[ci] FAIL: pytest exited ${PYTEST_RC} — the gate blocks the push."
    exit "${PYTEST_RC}"
fi
# KC-22 (#27): the DIFF-COVERAGE gate (changed kimcad lines >=80% overall, >=70% per module of
# >=20 changed lines) runs on incoming PRs in the hosted PR smoke (.github/workflows/pr-smoke.yml),
# which has the PR base to diff against — this self-hosted gate runs on push to main (where
# main already == HEAD, so there is nothing to diff). To self-check a branch locally before a PR:
#   .venv/Scripts/python -m pytest -q --cov=kimcad --cov-report=xml \
#     && .venv/Scripts/python scripts/check_diff_coverage.py coverage.xml --compare-branch origin/main
# (scripts/check_diff_coverage.py is the portable, unit-tested gate — see tests/test_check_diff_coverage.py.)
# KC-20 (#25): the Playwright e2e browser suite (tests/e2e/) runs as part of the pytest invocation
# above — it drives the real `kimcad web --demo` SPA in headless Chromium. It is gated by the
# `needs_browser` marker: where Chromium is installed (the provisioned gate box; ci.yml runs
# `playwright install chromium`) it RUNS; elsewhere (a fresh clone, the hosted fork-PR smoke) it
# SKIPS cleanly. Playwright is intentionally NOT in requirements.lock (test-only browser tooling).
# Coupling note (DOC-5): the design/on-ramp/export journeys ALSO carry `real_tool` because demo
# mode renders with the real OpenSCAD binary and the export journey slices with OrcaSlicer — so on
# a Chromium-present / binaries-absent box those journeys SKIP (and the print-path e2e goes
# unproven), the same live-tool contract the OrcaSlicer warning below covers.
# Frontend unit tests (vitest) + build-reproducibility check. The committed SPA build is what
# ships, so a toolchain-less environment doesn't fail the gate — it skips with a note (unless
# KIMCAD_RELEASE=1, which hard-fails so a release tag is never cut without the SPA gate). On a
# dev box with the deps installed, a vitest failure OR a committed-build drift blocks the push.
# The portable Node toolchain (repo-local tools/node22, or the machine CI copy) joins PATH so
# the frontend gate runs even when no system Node is installed — Node stays build-time only.
if [ -d tools/node22 ]; then
    PATH="$(pwd)/tools/node22:$PATH"
elif [ -d /c/kimcad-ci-tools/node22 ]; then
    PATH="/c/kimcad-ci-tools/node22:$PATH"
fi
if [ -d frontend/node_modules ] && command -v npm >/dev/null 2>&1; then
    echo "[ci] frontend tests (vitest)..."
    npm --prefix frontend run test
    echo "[ci] frontend build reproducibility (committed output == fresh build)..."
    npm --prefix frontend run build >/dev/null
    # Gate-integrity 2026-06-13: `git diff --quiet` sees only TRACKED changes — a fresh build that
    # ADDS a net-new asset/chunk (untracked) would slip through. `git status --porcelain` also lists
    # untracked ('??') entries, so this catches additive drift too.
    if ! git diff --quiet -- src/kimcad/web || [ -n "$(git status --porcelain -- src/kimcad/web)" ]; then
        echo "[ci] FAIL: src/kimcad/web differs from a fresh build — rebuild + commit the SPA output:"
        git --no-pager status --porcelain -- src/kimcad/web
        exit 1
    fi
else
    echo "[ci] NOTE: frontend/node_modules or npm absent — vitest + build check SKIPPED (committed build unaffected)."
    if [ "${KIMCAD_RELEASE:-}" = "1" ]; then
        echo "[ci] RELEASE GATE: refusing — frontend toolchain absent, the SPA gate is unproven."
        exit 1
    fi
fi
# Warn loudly (don't fail — the binary is fetched separately) when the live slice/web tests
# would skip: that run did NOT prove the real OrcaSlicer CLI contract end to end, so a
# release tag should not be cut from it.
if [ -x tools/orcaslicer/orca-slicer.exe ] || [ -x tools/orcaslicer/orca-slicer ]; then
    echo "[ci] OK (live slicer tests ran — real CLI contract proven)"
else
    echo "[ci] WARNING: OrcaSlicer binary absent — live slice tests SKIPPED; the real"
    echo "[ci]          slicer CLI contract was NOT proven this run. Do not cut a release"
    echo "[ci]          tag from this run; fetch tools/ and re-run."
    # Hard gate for releases: set KIMCAD_RELEASE=1 to FAIL (not just warn) when the live
    # slicer tests couldn't run, so a tag is never cut from an unproven run. Normal dev
    # pushes (the binary is fetched separately) stay unblocked.
    if [ "${KIMCAD_RELEASE:-}" = "1" ]; then
        echo "[ci] RELEASE GATE: refusing — live slicer contract unproven."
        exit 1
    fi
fi
# TEST-001 (Stage 8): the CadQuery worker-sandbox RCE tests are `live` (need a <=3.13 + cadquery
# interpreter). If none is discoverable, those tests SKIP — so the security-critical second layer
# went unproven this run. Warn always; HARD-FAIL on a release, mirroring the OrcaSlicer gate, so a
# tag is never cut without the worker-sandbox contract proven.
if "$PY" -c "from kimcad.cadquery_runner import find_cadquery_interpreter as f; import sys; sys.exit(0 if f() else 1)" 2>/dev/null; then
    echo "[ci] OK (CadQuery interpreter present — worker-sandbox live tests ran)."
else
    echo "[ci] WARNING: no CadQuery interpreter found — the worker-sandbox (RCE) live tests"
    echo "[ci]          SKIPPED; the CadQuery second-layer contract was NOT proven this run."
    if [ "${KIMCAD_RELEASE:-}" = "1" ]; then
        echo "[ci] RELEASE GATE: refusing — CadQuery worker-sandbox contract unproven."
        exit 1
    fi
fi
