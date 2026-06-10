#!/bin/sh
# Local CI gate — the AUTHORITATIVE pre-push gate (run on Windows). It is a SUPERSET of
# hosted CI: ruff + the full pytest suite (incl. the live OrcaSlicer slice) + frontend
# vitest + SPA build-reproducibility + release-mode live-tool proof. Hosted GitHub Actions
# (.github/workflows/ci.yml) is an intentionally PARTIAL smoke check (Python lint + pytest
# only, Linux) and is not equivalent. Used by the pre-push hook (.githooks/pre-push) and
# runnable by hand.
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
echo "[ci] pytest..."
# -ra surfaces skip reasons so a green run without the bundled OrcaSlicer binary can't be
# mistaken for one that proved the real slicer contract (TEST-002).
"$PY" -m pytest -q -ra
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
    if ! git diff --quiet -- src/kimcad/web; then
        echo "[ci] FAIL: src/kimcad/web differs from a fresh build — rebuild + commit the SPA output:"
        git --no-pager diff --stat -- src/kimcad/web
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
