"""Shared test fixtures (TEST-007).

``FakeProvider`` and the box renderer were duplicated verbatim in test_pipeline.py
and test_webapp.py. They are hoisted here as importable helpers plus fixtures so both
suites — and the new ones — share one definition. The helpers are plain
classes/functions (not just fixtures) because several existing tests construct a fresh
provider/renderer pair *inside* the test body (e.g. to assert call counts after a
retry), which a session/function fixture can't express cleanly.

BAMBU / PLA are the same fixed Printer/Material the existing suites pin.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from kimcad.config import Material, Printer
from kimcad.ir import DesignPlan
from kimcad.openscad_runner import RenderFailed, RenderResult, SanitizeResult

@pytest.fixture(autouse=True)
def _isolate_kimcad_home(tmp_path, monkeypatch):
    """Isolate the per-user ``~/.kimcad`` stores (settings / designs / history) to a fresh tmp dir
    for EVERY test, so no test reads or writes the developer's real files.

    Without this the model-status tests (which read the saved cloud setting since Slice 6 MS-3)
    were machine-dependent — green on CI's empty home, red on a machine whose ``~/.kimcad`` has cloud
    enabled. A test that needs its own path still overrides this (its monkeypatch runs after the
    fixture). Keeps the suite deterministic + the developer's real settings untouched."""
    from kimcad.config import Config

    home = tmp_path / "_kimcad_home"
    home.mkdir(exist_ok=True)
    monkeypatch.setattr(Config, "settings_path", lambda self: home / "settings.json")
    monkeypatch.setattr(Config, "designs_path", lambda self: home / "designs")
    monkeypatch.setattr(Config, "history_path", lambda self: home / "history.json")
    return home


BAMBU = Printer(
    key="bambu_p2s",
    name="Bambu Lab P2S",
    build_volume=(256, 256, 256),
    nozzle_diameter=0.4,
)
PLA = Material(
    key="pla", name="PLA", nozzle_temp=210, bed_temp=55, wall_multiplier=2.0, shrinkage=0.002
)


class FakeProvider:
    """LLM-free provider returning a fixed plan and SCAD; counts its calls."""

    def __init__(self, plan: DesignPlan, scad: str = "use <library/box.scad>;\nbox(20,20,20);"):
        self._plan = plan
        self._scad = scad
        self.design_calls = 0
        self.openscad_calls = 0

    def generate_design_plan(self, prompt, printer, material, history=None):  # noqa: ANN001
        self.design_calls += 1
        return self._plan

    def generate_openscad(self, plan, printer, material, history=None):  # noqa: ANN001
        self.openscad_calls += 1
        return self._scad

    def describe_photo(self, image_bytes, printer, material):  # noqa: ANN001
        # Slice 7: a canned vision seed; count via photo_calls so a test can assert it ran.
        self.photo_calls = getattr(self, "photo_calls", 0) + 1
        return "a small box, roughly 80mm wide (a rough guess from the photo — no scale)"


def box_renderer(extents, *, fail_times=0):
    """A stub renderer that writes a real trimesh box STL, optionally failing first.

    Returns ``(render_fn, state)`` so a caller can assert how many times it ran.
    """
    state = {"n": 0}

    def render(scad, out_dir: Path, basename: str) -> RenderResult:
        state["n"] += 1
        if state["n"] <= fail_times:
            raise RenderFailed(1, "synthetic render failure")
        path = out_dir / f"{basename}.stl"
        trimesh.creation.box(extents=extents).export(str(path))
        return RenderResult(
            output_path=path,
            output_format="stl",
            stdout="",
            stderr="",
            duration_s=0.01,
            sanitize=SanitizeResult(code=scad, removed=[]),
        )

    return render, state


def make_plan(bbox, **kw) -> DesignPlan:
    """A minimal sized DesignPlan for the fixtures' fake pipeline."""
    return DesignPlan(
        object_type="block",
        summary="a test block",
        bounding_box_mm=bbox,
        printer="bambu_p2s",
        material="pla",
        **kw,
    )


@pytest.fixture
def bambu() -> Printer:
    return BAMBU


@pytest.fixture
def pla() -> Material:
    return PLA


@pytest.fixture
def fake_provider_factory():
    """Factory fixture: call it with a plan (and optional SCAD) to get a FakeProvider."""
    return FakeProvider


@pytest.fixture
def box_renderer_factory():
    """Factory fixture: call it with extents to get ``(render_fn, state)``."""
    return box_renderer
