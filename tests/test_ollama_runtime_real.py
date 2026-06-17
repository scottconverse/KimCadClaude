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
