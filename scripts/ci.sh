#!/bin/sh
# Local CI gate — runs the same checks GitHub Actions would, on this machine.
# Used by the pre-push hook (.githooks/pre-push) and runnable by hand.
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
echo "[ci] pytest..."
# -ra surfaces skip reasons so a green run without the bundled OrcaSlicer binary can't be
# mistaken for one that proved the real slicer contract (TEST-002).
"$PY" -m pytest -q -ra
# Warn loudly (don't fail — the binary is fetched separately) when the live slice/web tests
# would skip: that run did NOT prove the real OrcaSlicer CLI contract end to end, so a
# release tag should not be cut from it.
if [ -x tools/orcaslicer/orca-slicer.exe ] || [ -x tools/orcaslicer/orca-slicer ]; then
    echo "[ci] OK (live slicer tests ran — real CLI contract proven)"
else
    echo "[ci] WARNING: OrcaSlicer binary absent — live slice tests SKIPPED; the real"
    echo "[ci]          slicer CLI contract was NOT proven this run. Do not cut a release"
    echo "[ci]          tag from this run; fetch tools/ and re-run."
fi
