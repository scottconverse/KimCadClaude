#!/usr/bin/env python
"""Fail-fast check that the HARD geometry runtime deps are genuinely usable (ENG-007).

scipy / networkx / manifold3d / lxml are pinned runtime deps in pyproject.toml, but a bare or
partial install does NOT raise on ``import trimesh`` — it silently DEGRADES: auto_orient stops
flattening, watertight / body_count drift, and ``trimesh.load`` of the rendered .3mf returns a
deferred-import placeholder that only fails deep inside a pipeline test. The result is ~30 tests
failing with misleading "logic" errors instead of one honest "missing dependency".

This script is the authoritative GATE copy of the probe in ``tests/conftest.py`` (keep the two in
sync). CI runs it right after ``pip install`` so a missing/broken compiled wheel turns the build RED
in seconds with a clear message — and a contributor can run it to diagnose a degraded environment:

    python scripts/check_geometry_backends.py
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile

REQUIRED = ("scipy", "networkx", "manifold3d", "lxml")


def check() -> list[str]:
    """Return a list of human-readable problems; empty list means every backend is usable."""
    problems = []
    # Actually IMPORT (execute) each backend, not just find_spec it: a broken/partial install (e.g.
    # a compiled wheel with an ABI mismatch) is discoverable but raises on import. "Usable", not
    # merely "installed", is the honest gate.
    for mod in REQUIRED:
        try:
            importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001 - any import failure means the backend is unusable
            problems.append(f"{mod} ({type(exc).__name__})")

    # The 3MF loader path is lazy in trimesh, so a real export->load round-trip is the only honest
    # check that lxml's reader is actually wired up rather than a placeholder that fails on use.
    try:
        import trimesh

        box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "probe.3mf")
            box.export(path)
            loaded = trimesh.load(path)
        geoms = list(loaded.geometry.values()) if hasattr(loaded, "geometry") else [loaded]
        if not any(len(getattr(g, "faces", ())) for g in geoms):
            problems.append("trimesh 3MF loader (round-trip produced no faces — lxml missing?)")
    except Exception as exc:  # noqa: BLE001 - a broken loader path is exactly what we must catch
        problems.append(f"trimesh 3MF loader ({type(exc).__name__}: {exc})")

    return problems


def main() -> int:
    problems = check()
    if problems:
        detail = ", ".join(problems)
        # ``::error::`` makes it a GitHub Actions annotation; harmless plain text elsewhere.
        print(f"::error::Missing/broken geometry backends: {detail}", file=sys.stderr)
        print("Install the geometry deps: pip install -e .", file=sys.stderr)
        return 1
    print("Geometry backends OK: scipy, networkx, manifold3d, lxml, and the 3MF loader round-trip.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
