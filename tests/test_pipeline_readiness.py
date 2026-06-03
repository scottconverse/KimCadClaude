"""Stage 7 Slice 3 — Smart Mesh readiness wired into the pipeline + the design API.

The pipeline computes a :class:`~kimcad.smart_mesh.MeshReadiness` for every built part (on the
report, so both the completed and gate-failed paths carry it) and, when PrintProof3D is
configured, validates a **bed-positioned** copy of the final hardened mesh first. These exercise
the gate-only path (engine absent — the default), the engine-integrated path (injected), the
bed-positioning contract, and the JSON the UI consumes.
"""

from __future__ import annotations

from pathlib import Path

import trimesh

from kimcad.config import Config
from kimcad.history import HistoryStore
from kimcad.ir import DesignPlan
from kimcad.pipeline import Pipeline, PipelineStatus
from kimcad.smart_mesh import MeshReadiness, PrintProofIssue, PrintProofReport, Risk
from kimcad.webapp import _readiness_payload, _report_payload

from conftest import BAMBU, PLA, FakeProvider
from conftest import box_renderer as _box_renderer


def _plan(object_type: str, *, dimensions=None, bbox=None) -> DesignPlan:
    return DesignPlan(
        object_type=object_type,
        summary="t",
        dimensions=dimensions or {},
        bounding_box_mm=bbox,
        printer="bambu_p2s",
        material="pla",
    )


def _pipeline(provider, renderer, **kw) -> Pipeline:
    return Pipeline(Config.load(), BAMBU, PLA, provider, renderer=renderer, **kw)


# --- readiness is always attached, on both the completed and the gate-failed paths ----------

def test_completed_run_attaches_a_gate_based_readiness(tmp_path):
    # No PrintProof3D configured (the default) -> readiness rides on KimCad's own gate.
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2})
    renderer, _ = _box_renderer((80, 60, 40))
    result = _pipeline(FakeProvider(plan), renderer).run("a box", tmp_path)

    assert result.status is PipelineStatus.completed
    r = result.report.readiness
    assert isinstance(r, MeshReadiness)
    assert r.tone == "pass" and r.verdict == "Ready to print"
    assert r.score >= 80
    # Engine absent -> medium confidence, gate-only attribution (honest about what backed it).
    assert r.confidence == "Medium"
    assert r.attribution == "KimCad printability gate"


def test_gate_failed_run_still_attaches_readiness(tmp_path):
    # A too-wrong template part fails the gate; the readiness must still be present (on the
    # report) and must read "not print-ready" — the card is shown even when the part is blocked.
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40})
    renderer, _ = _box_renderer((20, 20, 20))  # wrong size -> dim-mismatch FAIL
    result = _pipeline(FakeProvider(plan), renderer).run("a box", tmp_path)

    assert result.status is PipelineStatus.gate_failed
    r = result.report.readiness
    assert isinstance(r, MeshReadiness)
    assert r.tone == "fail" and r.verdict == "Not print-ready"
    assert any(risk.tone == "fail" for risk in r.risks)


def test_readiness_is_recomputed_on_a_live_slider_rerender(tmp_path):
    # The re-render path runs the same assemble tail, so the card updates from server truth.
    # A clamped-but-valid wall keeps the part print-ready (the template's range-bounding is the
    # safety net — it won't let the wall go unprintable); the readiness is still freshly computed.
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2.0})
    pipe = _pipeline(FakeProvider(plan), _box_renderer((80, 60, 40))[0])
    design = pipe.run("a box", tmp_path)
    assert design.report.readiness.tone == "pass"

    valid = pipe.rerender(design.plan, "snap_box",
                          {"width": 80, "depth": 60, "height": 40, "wall": 1.5}, tmp_path)
    assert valid.report.readiness is not None
    # Readiness is gate-consistent: a passing re-render reads print-ready.
    assert valid.report.readiness.tone == "pass"
    assert valid.report.gate_status == "pass"


def test_readiness_drops_to_fail_when_the_rerender_gate_fails(tmp_path):
    # When a re-render flips a part to gate-FAIL (here the stub renders the wrong size, so the
    # envelope no longer matches the requested one), the readiness must follow it to "fail".
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2.0})
    # Stub always renders an 80mm part; re-rendering at a 200mm envelope -> dim-mismatch FAIL.
    pipe = _pipeline(FakeProvider(plan), _box_renderer((80, 60, 40))[0])
    pipe.run("a box", tmp_path)

    big = pipe.rerender(plan, "snap_box",
                        {"width": 200, "depth": 150, "height": 120, "wall": 2.0}, tmp_path)
    assert big.status is PipelineStatus.gate_failed
    assert big.report.readiness is not None
    assert big.report.readiness.tone == "fail"
    assert big.report.readiness.verdict == "Not print-ready"


# --- PrintProof3D integration: bed-positioning + the deeper verdict folds in ------------------

def test_printproof3d_validates_a_bed_positioned_mesh_and_folds_in(tmp_path, monkeypatch):
    captured: dict[str, list[float]] = {}

    def fake_validate(mesh_path, printer, material, *, binary, **kw):
        # The contract: the caller bed-positions first, so the STL we get has its min-corner
        # at the bed origin (else PrintProof3D would false-flag MODEL_OUT_OF_BOUNDS).
        mesh = trimesh.load(str(mesh_path))
        captured["min"] = [float(c) for c in mesh.bounds[0]]
        assert binary == Path("fake-pp3d.exe")
        return PrintProofReport(
            status="warning",
            confidence_level="high",
            issues=(
                PrintProofIssue(
                    id="OVERHANG_UNSUPPORTED",
                    message="A 55 deg overhang has no support.",
                    severity="major",
                    suggested_fixes=("Add supports under the overhang.",),
                    region="overhang",
                ),
            ),
        )

    monkeypatch.setattr("kimcad.pipeline.validate_model", fake_validate)

    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2})
    renderer, _ = _box_renderer((80, 60, 40))
    pipe = _pipeline(FakeProvider(plan), renderer)
    # Pretend the engine is configured (the file doesn't need to exist — validate_model is faked).
    monkeypatch.setattr(pipe.config, "printproof3d_binary", lambda: Path("fake-pp3d.exe"))

    result = pipe.run("a box", tmp_path)

    assert result.status is PipelineStatus.completed
    # Bed-positioned: min-corner is at (0, 0, 0) within mesh-float noise.
    assert "min" in captured
    for component in captured["min"]:
        assert abs(component) <= 0.01, f"mesh not bed-positioned: min={captured['min']}"
    # The engine's verdict folded in: warn tone, high confidence, engine attribution, its fix.
    r = result.report.readiness
    assert r.tone == "warn"
    assert r.confidence == "High"
    assert r.attribution == "PrintProof3D validation engine"
    assert "Add supports under the overhang." in r.recommendations
    assert any("overhang" in risk.title.lower() for risk in r.risks)


def test_rerender_does_not_run_the_engine(tmp_path, monkeypatch):
    # SLICE3-001: the engine validates once on the initial design; a live-slider re-render must
    # NOT spawn the deep-validation subprocess (it would block a debounced drag). The re-render
    # falls back to the instant, honestly-attributed gate-only readiness.
    calls = {"n": 0}

    def spy_validate(mesh_path, printer, material, *, binary, **kw):
        calls["n"] += 1
        return PrintProofReport(status="pass", confidence_level="high", issues=())

    monkeypatch.setattr("kimcad.pipeline.validate_model", spy_validate)
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2})
    renderer, _ = _box_renderer((80, 60, 40))
    pipe = _pipeline(FakeProvider(plan), renderer)
    monkeypatch.setattr(pipe.config, "printproof3d_binary", lambda: Path("fake-pp3d.exe"))

    design = pipe.run("a box", tmp_path)
    assert calls["n"] == 1, "the engine validates once on the initial design"
    assert design.report.readiness.attribution == "PrintProof3D validation engine"

    r = pipe.rerender(design.plan, "snap_box",
                      {"width": 80, "depth": 60, "height": 40, "wall": 1.5}, tmp_path)
    assert calls["n"] == 1, "a live-slider re-render must NOT spawn the engine subprocess"
    assert r.report.readiness is not None
    assert r.report.readiness.attribution == "KimCad printability gate"  # gate-only on a drag


def test_to_text_renders_the_readiness_block(tmp_path, monkeypatch):
    # SLICE3-002: the new to_text() readiness block (and its risk / recommendation lines) renders.
    def fake_validate(mesh_path, printer, material, *, binary, **kw):
        return PrintProofReport(
            status="warning",
            confidence_level="high",
            issues=(
                PrintProofIssue(
                    id="OVERHANG_UNSUPPORTED",
                    message="A 55 deg overhang has no support.",
                    severity="major",
                    suggested_fixes=("Add supports under the overhang.",),
                    region="overhang",
                ),
            ),
        )

    monkeypatch.setattr("kimcad.pipeline.validate_model", fake_validate)
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2})
    renderer, _ = _box_renderer((80, 60, 40))
    pipe = _pipeline(FakeProvider(plan), renderer)
    monkeypatch.setattr(pipe.config, "printproof3d_binary", lambda: Path("fake-pp3d.exe"))

    result = pipe.run("a box", tmp_path)
    text = result.report.to_text()
    assert "Readiness:" in text
    assert result.report.readiness.verdict in text  # the verdict string is shown
    assert "Risk:" in text  # the overhang risk surfaced
    assert "Suggest:" in text  # the engine's fix surfaced as a recommendation


def test_printproof3d_failure_never_breaks_the_build(tmp_path, monkeypatch):
    # If validate_model itself blows up (it shouldn't — but defense in depth), the pipeline
    # must still complete on the gate-only readiness, never crash.
    def boom(*a, **k):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr("kimcad.pipeline.validate_model", boom)
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2})
    renderer, _ = _box_renderer((80, 60, 40))
    pipe = _pipeline(FakeProvider(plan), renderer)
    monkeypatch.setattr(pipe.config, "printproof3d_binary", lambda: Path("fake-pp3d.exe"))

    result = pipe.run("a box", tmp_path)
    assert result.status is PipelineStatus.completed
    # Degraded cleanly to the gate-only verdict.
    assert result.report.readiness is not None
    assert result.report.readiness.attribution == "KimCad printability gate"


# --- the learning store: comparison + recording ----------------------------------------------

def test_no_history_store_means_no_comparison(tmp_path):
    # The default pipeline has no history store -> no comparison line, no side effects.
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2})
    renderer, _ = _box_renderer((80, 60, 40))
    result = _pipeline(FakeProvider(plan), renderer).run("a box", tmp_path)
    assert result.report.readiness.comparison is None
    assert "print history" not in result.report.readiness.attribution


def test_history_comparison_folds_in_and_the_build_is_recorded(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    # Seed two prior, lower-scoring box prints so the new build ranks against them.
    from kimcad.history import PrintRecord
    store.record(PrintRecord("box", 50, "pass", "PLA", 80.0))
    store.record(PrintRecord("box", 60, "pass", "PLA", 80.0))

    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2})
    renderer, _ = _box_renderer((80, 60, 40))
    pipe = Pipeline(Config.load(), BAMBU, PLA, FakeProvider(plan), renderer=renderer, history=store)
    result = pipe.run("a box", tmp_path)

    r = result.report.readiness
    assert r.comparison is not None
    assert "past" in r.comparison  # a factual ranking line
    assert "your local build history" in r.attribution  # attribution augmented honestly

    # The build was recorded AFTER comparing, so the store now has 3 records and the comparison
    # above ranked against the 2 PRIOR ones (not itself).
    records = store.load()
    assert len(records) == 3
    assert records[-1].object_type == "box"
    assert records[-1].score == r.score


def test_rerender_does_not_record_history(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2})
    renderer, _ = _box_renderer((80, 60, 40))
    pipe = Pipeline(Config.load(), BAMBU, PLA, FakeProvider(plan), renderer=renderer, history=store)

    pipe.run("a box", tmp_path)
    assert len(store.load()) == 1  # the initial design recorded once

    pipe.rerender(plan, "snap_box",
                  {"width": 80, "depth": 60, "height": 40, "wall": 1.5}, tmp_path)
    pipe.rerender(plan, "snap_box",
                  {"width": 90, "depth": 60, "height": 40, "wall": 1.5}, tmp_path)
    # A live-slider drag is not a new design — the store must NOT grow per drag.
    assert len(store.load()) == 1


# --- the design API exposes readiness --------------------------------------------------------

def test_report_payload_includes_the_readiness_block(tmp_path):
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2})
    renderer, _ = _box_renderer((80, 60, 40))
    result = _pipeline(FakeProvider(plan), renderer).run("a box", tmp_path)

    payload = _report_payload(result.report)
    assert "readiness" in payload
    rp = payload["readiness"]
    assert rp["score"] == result.report.readiness.score
    assert rp["verdict"] == "Ready to print"
    assert rp["tone"] == "pass"
    assert rp["confidence"] == "Medium"
    assert rp["attribution"] == "KimCad printability gate"
    assert isinstance(rp["risks"], list)
    assert isinstance(rp["recommendations"], list)


def test_readiness_payload_shapes_risks_and_handles_none():
    assert _readiness_payload(None) is None
    readiness = MeshReadiness(
        score=70,
        verdict="Printable with notes",
        tone="warn",
        confidence="High",
        risks=[Risk("Overhang unsupported", "A 55 deg overhang.", "warn")],
        recommendations=["Add supports."],
        comparison="Matches your strongest past prints.",
        attribution="PrintProof3D validation engine",
    )
    payload = _readiness_payload(readiness)
    assert payload["score"] == 70
    assert payload["risks"] == [
        {"title": "Overhang unsupported", "detail": "A 55 deg overhang.", "tone": "warn"}
    ]
    assert payload["recommendations"] == ["Add supports."]
    assert payload["comparison"] == "Matches your strongest past prints."
