"""Stage 7 Slice 1 — Smart Mesh readiness model + scoring.

`assess_readiness` is pure, so these build synthetic gate results / mesh reports / PrintProof3D
reports and assert the synthesized verdict directly — no model, slicer, or PrintProof3D binary.
"""

from __future__ import annotations

from kimcad.printability import Finding, GateResult, Level
from kimcad.smart_mesh import (
    MeshReadiness,
    PrintProofIssue,
    PrintProofReport,
    assess_readiness,
)
from kimcad.validation import MeshReport


def _gate(*findings: tuple[Level, str, str]) -> GateResult:
    return GateResult(findings=[Finding(lvl, code, msg) for (lvl, code, msg) in findings])


def _mesh(*, watertight: bool = True, errors: list[str] | None = None) -> MeshReport:
    return MeshReport(
        watertight=watertight,
        repaired=False,
        repairs=[],
        vertices=100,
        faces=200,
        volume_mm3=1000.0,
        bounding_box_mm=(20.0, 20.0, 20.0),
        n_bodies=1,
        stray_bodies=0,
        errors=errors or [],
    )


# --- the three KimCad-gate-only verdicts ----------------------------------------------------

def test_clean_pass_is_ready_to_print():
    r = assess_readiness(_gate((Level.PASS, "dim.match", "all axes ok")), _mesh())
    assert isinstance(r, MeshReadiness)
    assert r.verdict == "Ready to print"
    assert r.tone == "pass"
    assert r.score == 92
    assert r.risks == []  # PASS findings are not risks
    assert r.confidence == "Medium"  # no PrintProof3D engine ran
    assert r.attribution == "KimCad printability gate"
    assert r.sources == ["printability-gate"]


def test_gate_warn_is_printable_with_notes():
    r = assess_readiness(_gate((Level.WARN, "wall.thin", "a wall is below the minimum")), _mesh())
    assert r.verdict == "Printable with notes"
    assert r.tone == "warn"
    assert r.score == 70
    assert len(r.risks) == 1
    assert r.risks[0].tone == "warn"
    assert r.risks[0].title == "Walls below the minimum"  # mapped from the code


def test_gate_fail_is_not_print_ready():
    r = assess_readiness(_gate((Level.FAIL, "dim.mismatch", "X is 30mm, target 50mm")), _mesh())
    assert r.verdict == "Not print-ready"
    assert r.tone == "fail"
    assert r.score == 38
    assert r.risks[0].tone == "fail"
    assert r.risks[0].title == "Dimensions off target"


# --- PrintProof3D folds in -------------------------------------------------------------------

def test_printproof_major_issue_folds_in_as_a_warn_risk_and_recommendation():
    pp = PrintProofReport(
        status="warning",
        confidence_level="high",
        issues=(PrintProofIssue(
            id="OVERHANG_UNSUPPORTED",
            message="A 50 deg overhang on the arm has no support.",
            severity="major",
            suggested_fixes=("Add supports under the arm.",),
            region="overhang",
        ),),
    )
    r = assess_readiness(_gate((Level.PASS, "dim.match", "ok")), _mesh(), printproof=pp)
    assert "printproof3d" in r.sources
    assert r.confidence == "High"  # the deeper engine ran
    assert r.attribution == "PrintProof3D validation engine"
    titles = [risk.title for risk in r.risks]
    assert "Overhang unsupported" in titles  # humanized from the id
    assert any(risk.tone == "warn" for risk in r.risks)
    assert r.score == 92 - 18  # major penalty
    assert "Add supports under the arm." in r.recommendations
    # an overhang risk adds the orientation recommendation
    assert any("auto-orientation" in rec for rec in r.recommendations)
    assert r.verdict == "Printable with notes"  # a risk drops a clean pass


def test_printproof_blocker_makes_it_not_print_ready():
    pp = PrintProofReport(
        status="fail",
        confidence_level="high",
        issues=(PrintProofIssue("BUILD_VOLUME_EXCEEDED", "Part is 300mm, bed is 256mm.",
                                "blocker", suggested_fixes=("Scale down or split.",)),),
    )
    r = assess_readiness(_gate((Level.PASS, "dim.match", "ok")), _mesh(), printproof=pp)
    assert r.verdict == "Not print-ready"
    assert r.tone == "fail"
    assert r.score == max(0, 92 - 60)
    assert any(risk.tone == "fail" for risk in r.risks)


def test_printproof_fail_status_forces_not_ready_even_with_only_a_major_issue():
    # SM-001: the engine's overall status is authoritative -- a "fail" report is "Not
    # print-ready" even when its worst individual issue is only "major" (whose penalty alone
    # wouldn't sink the score below 50). The card must never be rosier than the engine.
    pp = PrintProofReport("fail", "high",
                          issues=(PrintProofIssue("THERMAL_RISK", "runs hot", "major"),))
    r = assess_readiness(_gate((Level.PASS, "dim.match", "ok")), _mesh(), printproof=pp)
    assert r.verdict == "Not print-ready"
    assert r.tone == "fail"
    assert r.score == 92 - 18  # the major penalty still applies, but status drives the verdict


def test_printproof_warning_status_drops_a_clean_pass_to_with_notes():
    # SM-001: a "warning" status forces at least "Printable with notes", even on an otherwise
    # clean part with no surfaced issues.
    pp = PrintProofReport("warning", "high", issues=())
    r = assess_readiness(_gate((Level.PASS, "dim.match", "ok")), _mesh(), printproof=pp)
    assert r.verdict == "Printable with notes"
    assert r.tone == "warn"


def test_unknown_gate_code_uses_the_message_head_as_the_risk_title():
    # SM-002: an unmapped gate code falls back to the message's first clause, truncated, ASCII.
    long_msg = "the support under the cantilever may detach mid-print because it is tall and thin"
    r = assess_readiness(_gate((Level.WARN, "novel.check", long_msg)), _mesh())
    assert len(r.risks) == 1
    title = r.risks[0].title
    assert title.startswith("the support under the cantilever")
    assert len(title) <= 51 and title.endswith("...")  # 48 chars + "..."
    assert title.isascii()  # no non-ASCII in a user-facing title


def test_printproof_nit_does_not_surface_as_a_risk():
    pp = PrintProofReport("pass", "high",
                          issues=(PrintProofIssue("MINOR_THING", "cosmetic", "nit"),))
    r = assess_readiness(_gate((Level.PASS, "dim.match", "ok")), _mesh(), printproof=pp)
    assert r.risks == []  # a nit is not a risk
    assert r.score == 91  # only a 1-point nit penalty
    assert r.verdict == "Ready to print"  # still clean


# --- confidence / mesh-analysability ---------------------------------------------------------

def test_unanalysable_mesh_drops_confidence_to_low():
    r = assess_readiness(
        _gate((Level.PASS, "dim.match", "ok")),
        _mesh(errors=["body count could not be computed"]),
    )
    assert r.confidence == "Low"
    assert "partly analyzable" in r.attribution


def test_unanalysable_mesh_keeps_confidence_low_even_when_the_engine_ran():
    # TEST-S7-002: an unanalysable mesh forces Low confidence EVEN when the deeper PrintProof3D
    # engine ran (Low must win over the engine's High) — the card hedges on exactly the parts
    # KimCad couldn't fully measure, never overstating certainty.
    engine = PrintProofReport(status="pass", confidence_level="high", issues=())
    r = assess_readiness(
        _gate((Level.PASS, "dim.match", "ok")),
        _mesh(errors=["body count could not be computed"]),
        printproof=engine,
    )
    assert r.confidence == "Low"  # not "High", despite the engine running
    assert "partly analyzable" in r.attribution


# --- score clamping, material rec, dedupe, purity --------------------------------------------

def test_score_is_clamped_to_0_100():
    pp = PrintProofReport("fail", "high", issues=tuple(
        PrintProofIssue(f"X{i}", "m", "blocker") for i in range(5)
    ))
    r = assess_readiness(_gate((Level.FAIL, "dim.mismatch", "wrong")), _mesh(), printproof=pp)
    assert 0 <= r.score <= 100
    assert r.score == 0  # 38 base - 5*60, clamped


def test_material_recommendation_on_a_non_fail_part():
    r = assess_readiness(_gate((Level.PASS, "dim.match", "ok")), _mesh(), material_name="PLA")
    assert any("PLA" in rec for rec in r.recommendations)


def test_no_material_recommendation_on_a_failed_part():
    r = assess_readiness(_gate((Level.FAIL, "dim.mismatch", "x")), _mesh(), material_name="PLA")
    assert not any("Slice for PLA" in rec for rec in r.recommendations)


def test_recommendations_are_deduped():
    pp = PrintProofReport("warning", "high", issues=(
        PrintProofIssue("A", "m", "major", suggested_fixes=("Do the thing.",)),
        PrintProofIssue("B", "m", "major", suggested_fixes=("Do the thing.",)),  # same fix twice
    ))
    r = assess_readiness(_gate((Level.PASS, "dim.match", "ok")), _mesh(), printproof=pp)
    assert r.recommendations.count("Do the thing.") == 1


def test_assess_readiness_is_pure_same_inputs_same_output():
    gate = _gate((Level.WARN, "wall.thin", "thin"))
    mesh = _mesh()
    pp = PrintProofReport("warning", "high",
                          issues=(PrintProofIssue("OVERHANG", "m", "major"),))
    a = assess_readiness(gate, mesh, material_name="PLA", printproof=pp)
    b = assess_readiness(gate, mesh, material_name="PLA", printproof=pp)
    assert a == b
