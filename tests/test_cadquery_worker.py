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


def test_worker_deny_network_blocks_fd_to_socket_factories():
    """ENG-GG-004: a smuggled fd must not be turnable into a live socket. ``fromfd``/``dup``
    (and Windows-only ``fromshare``) are neutralized alongside the constructors, so reconstituting
    a socket from a descriptor is blocked too. ``fromshare`` is skipped where the platform lacks
    it (non-Windows) — exactly the hasattr-guarded behaviour the worker relies on."""
    code = (
        f"import sys; sys.path.insert(0, r'{_SRC}')\n"
        "from kimcad import cadquery_worker\n"
        "cadquery_worker._deny_network()\n"
        "import socket\n"
        "out = []\n"
        "try:\n"
        "    socket.fromfd(0, socket.AF_INET, socket.SOCK_STREAM); out.append('FROMFD-OPENED')\n"
        "except PermissionError:\n"
        "    out.append('fromfd-blocked')\n"
        "try:\n"
        "    socket.dup(0); out.append('DUP-OPENED')\n"
        "except PermissionError:\n"
        "    out.append('dup-blocked')\n"
        "if hasattr(socket, 'fromshare'):\n"
        "    try:\n"
        "        socket.fromshare(b''); out.append('FROMSHARE-OPENED')\n"
        "    except PermissionError:\n"
        "        out.append('fromshare-blocked')\n"
        "else:\n"
        "    out.append('fromshare-absent')\n"
        "print('|'.join(out))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    res = r.stdout.strip()
    assert "fromfd-blocked" in res, f"fromfd not denied: {res!r} / stderr={r.stderr[-300:]!r}"
    assert "dup-blocked" in res, f"dup not denied: {res!r}"
    # fromshare is Windows-only; either it's blocked or it doesn't exist — never opened.
    assert ("fromshare-blocked" in res) or ("fromshare-absent" in res), f"fromshare path: {res!r}"
    assert "OPENED" not in res, f"an fd-to-socket factory was NOT denied: {res!r}"


def test_deny_network_is_called_before_exec_in_source():
    """TEST-GG-003: the network-deny hook is worthless if it runs AFTER the untrusted script.
    Pin the ordering at the source level — ``_deny_network()`` MUST be invoked before ``exec(``
    in the worker — so a future refactor can't silently move the deny below the exec."""
    src = (_SRC / "kimcad" / "cadquery_worker.py").read_text(encoding="utf-8")
    # The CALL site, not the `def _deny_network()` definition — match the indented invocation.
    deny_at = src.find("\n    _deny_network()")
    exec_at = src.find("exec(compiled")
    assert deny_at != -1, "no _deny_network() call found in cadquery_worker.py"
    assert exec_at != -1, "no exec(compiled ...) call found in cadquery_worker.py"
    assert deny_at < exec_at, (
        f"_deny_network() (idx {deny_at}) must be called BEFORE exec( (idx {exec_at}) — "
        "network egress must be denied before untrusted code runs"
    )
