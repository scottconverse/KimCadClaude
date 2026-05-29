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
"$PY" -m pytest -q
echo "[ci] OK"
