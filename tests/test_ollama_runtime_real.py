"""Real-tool integration: the managed-runtime path exercised against an ACTUAL Ollama.

The b5 lesson — prove the effect against the real tool, don't mock it away. The orchestration in
ollama_runtime is unit-tested with injected effects (test_ollama_runtime.py); this drives the REAL
installed Ollama: resolve the real executable, then ensure it's serving and confirm the real HTTP
endpoint answers.

Gated on Ollama presence (not the `real_tool` marker, which means OpenSCAD/OrcaSlicer here): runs on
a box with Ollama (the dev/CI box always has it), skips cleanly on a fresh clone without it.

The portable-FETCH path (downloading the real ~1.4 GB ollama-windows-amd64.zip) is proven manually
end-to-end and recorded in docs/audits/coder-ui-qa-test-coldstart-2026-06-17/ — NOT auto-run here, as
a 1.4 GB download per gate is wasteful; the fetch logic is unit-tested with a synthetic zip
(test_ollama_fetch.py) and pinned by SHA-256.
"""

from __future__ import annotations

import pytest

from kimcad import ollama_runtime as ort

_OLLAMA_AVAILABLE = ort.is_server_up() or ort.resolve_ollama_exe() is not None
_skip = pytest.mark.skipif(not _OLLAMA_AVAILABLE, reason="no system Ollama available on this box")


@_skip
def test_resolve_finds_the_real_ollama_executable() -> None:
    exe = ort.resolve_ollama_exe()
    assert exe is not None and exe.exists(), "expected to resolve a real ollama executable"


@_skip
def test_ensure_serving_reuses_or_starts_the_real_ollama() -> None:
    # Reuse a running Ollama, or start the real binary; either way the real endpoint must answer.
    st = ort.ensure_serving()
    assert st.running is True, f"ensure_serving did not reach a running server: {st}"
    assert ort.is_server_up() is True


@_skip
def test_start_serve_spawns_a_real_server_on_an_alt_port_and_tears_down() -> None:
    """TEST-GG-001: the reuse branch above never spawns. This forces the REAL spawn path —
    start `ollama serve` on a free alternate loopback port (so it can't collide with the system
    :11434), poll until the real HTTP endpoint answers, then tear it down and confirm it's gone
    (the ENG-GG-001 no-orphan guarantee, proven against the real binary)."""
    import socket
    import time

    exe = ort.resolve_ollama_exe()
    assert exe is not None and exe.exists()

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    host = f"127.0.0.1:{port}"
    base = f"http://127.0.0.1:{port}/v1"
    assert ort.is_server_up(base) is False, "alt port should be free before we spawn"

    proc = ort.start_serve(exe, host=host)
    try:
        up = False
        for _ in range(60):  # ~30s budget for a cold serve to answer
            if ort.is_server_up(base):
                up = True
                break
            time.sleep(0.5)
        assert up, "real `ollama serve` on the alt port never became healthy"
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()
    # No orphan: the spawned server is gone after teardown.
    time.sleep(1.0)
    assert ort.is_server_up(base) is False, "spawned server still answering after teardown (orphan!)"
