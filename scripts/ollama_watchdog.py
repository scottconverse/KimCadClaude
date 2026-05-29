#!/usr/bin/env python3
"""Keep the local Ollama server alive during long benchmark runs.

On a CPU-only box the model server can crash under sustained load. This polls the
Ollama endpoint and relaunches ``ollama serve`` whenever it goes unreachable. Run it
in the background alongside ``kimcad bench``; combined with the LLM client's
connection-retry, a single server crash no longer fails the whole batch.

    python scripts/ollama_watchdog.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ENDPOINT = "http://localhost:11434/api/tags"
POLL_S = 10
RESTART_SETTLE_S = 20


def ollama_path() -> str | None:
    """Locate the ollama executable on PATH or in the default Windows install dir."""
    found = shutil.which("ollama")
    if found:
        return found
    cand = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return str(cand) if cand.exists() else None


def is_up(timeout: float = 5.0) -> bool:
    """True if the Ollama HTTP endpoint is reachable."""
    try:
        urllib.request.urlopen(ENDPOINT, timeout=timeout)
        return True
    except Exception:
        return False


def main() -> int:
    exe = ollama_path()
    if exe is None:
        print("ollama executable not found", file=sys.stderr)
        return 1
    restarts = 0
    print(f"[watchdog] watching {ENDPOINT} (every {POLL_S}s); ollama at {exe}", flush=True)
    while True:
        if not is_up():
            restarts += 1
            print(f"[watchdog] Ollama unreachable — restart #{restarts}", flush=True)
            subprocess.Popen([exe, "serve"])  # no-op if one is already binding
            time.sleep(RESTART_SETTLE_S)
        time.sleep(POLL_S)


if __name__ == "__main__":
    raise SystemExit(main())
