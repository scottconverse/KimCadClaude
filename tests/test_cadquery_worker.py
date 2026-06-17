"""ENG-004 (audit-team-b4 watchlist → fixed): the CadQuery worker denies network egress before
running untrusted code (a geometry worker needs none).

Proven in a FRESH SUBPROCESS — the way the worker actually runs — so denying network never patches
the pytest process's own socket module (which the webapp/connector tests rely on). This is the
no-false-greens proof for the worker's network confinement.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"


def test_worker_deny_network_blocks_socket_creation():
    code = (
        f"import sys; sys.path.insert(0, r'{_SRC}')\n"
        "from kimcad import cadquery_worker\n"
        "cadquery_worker._deny_network()\n"
        "import socket\n"
        "out = []\n"
        "try:\n"
        "    socket.socket(); out.append('SOCKET-OPENED')\n"
        "except PermissionError:\n"
        "    out.append('socket-blocked')\n"
        "try:\n"
        "    socket.create_connection(('127.0.0.1', 9), timeout=1); out.append('CONN-OPENED')\n"
        "except PermissionError:\n"
        "    out.append('conn-blocked')\n"
        "print('|'.join(out))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    res = r.stdout.strip()
    assert "socket-blocked" in res, f"socket() not denied: {res!r} / stderr={r.stderr[-300:]!r}"
    assert "conn-blocked" in res, f"create_connection not denied: {res!r}"
    assert "OPENED" not in res, f"network was NOT denied in the worker: {res!r}"


def test_deny_network_is_idempotent_and_best_effort():
    """Calling it twice (or where _socket is odd) must not raise — it's a defence-in-depth hook
    that should never crash the worker."""
    code = (
        f"import sys; sys.path.insert(0, r'{_SRC}')\n"
        "from kimcad import cadquery_worker\n"
        "cadquery_worker._deny_network(); cadquery_worker._deny_network()\n"
        "print('OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert r.stdout.strip() == "OK", f"_deny_network raised: {r.stderr[-300:]!r}"
