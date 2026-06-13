"""Stage 5 — the deterministic-template benchmark/proof (kimcad.template_bench).

Two layers, mirroring the rest of the template suite:
- offline contract tests (no binary): the perturbation stays in range, the report formats and
  is console-safe, the no-model guard actually raises, and the ok/target logic is correct;
- a binary-gated live gate that renders + re-renders every family through the real pipeline and
  asserts the proof holds (watertight at the declared envelope, deterministic, no model call,
  under the non-flaky time ceiling). The <1 s interactive target is reported per family and
  documented in docs/benchmarks/, but the automated *gate* is the conservative ceiling so the
  suite can't flake on a loaded box. Skipped offline.
"""

from __future__ import annotations

import pytest

from kimcad.config import Config
from kimcad.template_bench import (
    BBOX_TOLERANCE_MM,
    RERENDER_CEILING_S,
    RERENDER_TARGET_S,
    BenchReport,
    FamilyBench,
    _NoModelProvider,
    _perturb,
    benchmark_families,
    environment,
)
from kimcad.templates import clamp_values, default_registry


def _fb(name: str, **kw) -> FamilyBench:
    base = dict(
        rendered=True,
        watertight=True,
        gate_status="pass",
        bbox_error_mm=0.0,
        initial_render_s=0.2,
        rerender_s=0.3,
        deterministic_emit=True,
        error=None,
    )
    base.update(kw)
    return FamilyBench(name=name, **base)


# --- offline: perturbation, environment, guard ------------------------------------

@pytest.mark.parametrize("name", [f.name for f in default_registry().families()])
def test_perturb_is_in_range_and_changes_the_geometry(name):
    fam = default_registry().family(name)
    defaults = clamp_values(fam, {})
    perturbed = _perturb(fam, defaults)
    p0 = fam.params[0]
    # A real change to the first parameter, still inside its declared bounds.
    assert perturbed[p0.name] != defaults[p0.name]
    assert p0.min <= perturbed[p0.name] <= p0.max


def test_environment_reports_platform_and_python():
    env = environment()
    assert env["platform"] and env["python"]
    assert "processor" in env


def test_no_model_provider_raises_on_any_model_call():
    guard = _NoModelProvider()
    with pytest.raises(AssertionError, match="must not"):
        guard.generate_design_plan("prompt", None, None)
    with pytest.raises(AssertionError, match="must not"):
        guard.generate_openscad(None, None, None)


# --- offline: report logic + console safety ---------------------------------------

def test_family_ok_and_target_logic():
    assert _fb("a").ok and _fb("a").meets_target
    # over the envelope tolerance -> not ok
    assert not _fb("a", bbox_error_mm=BBOX_TOLERANCE_MM + 0.01).ok
    # over the ceiling -> not ok (and not target)
    slow = _fb("a", rerender_s=RERENDER_CEILING_S + 1)
    assert not slow.ok and not slow.meets_target
    # an error row is never ok
    assert not _fb("a", error="boom").ok
    # a non-deterministic emit (the rendered SCAD didn't match the pure template emit) -> not ok
    assert not _fb("a", deterministic_emit=False).ok
    # interactive-but-not-sub-second: ok (under ceiling) yet misses the <1 s target
    near = _fb("a", rerender_s=1.5)
    assert near.ok and not near.meets_target


def test_markdown_marks_an_over_target_family_as_not_under_1s():
    report = BenchReport(
        families=(_fb("snap_box", rerender_s=0.3), _fb("slowpoke", rerender_s=2.0)),
        environment=environment(),
        binary_present=True,
    )
    md = report.to_markdown()
    md.encode("cp1252")
    # the fast family is under 1s, the slow one is not — the column reflects both.
    fast = next(line for line in md.splitlines() if "`snap_box`" in line)
    slow = next(line for line in md.splitlines() if "`slowpoke`" in line)
    assert "| yes |" in fast  # Under-1s column = yes
    assert "| no |" in slow  # Under-1s column = no
    assert report.ok and not report.all_meet_target


def test_report_markdown_is_console_safe_and_has_verdict():
    report = BenchReport(
        families=(_fb("snap_box"), _fb("tube", rerender_s=0.4)),
        environment=environment(),
        binary_present=True,
    )
    md = report.to_markdown(date="2026-06-02")
    md.encode("cp1252")  # must not raise — printed to a cp1252 Windows console
    assert report.ok
    assert "PASS" in md
    assert "`snap_box`" in md and "`tube`" in md
    assert "2026-06-02" in md


def test_report_flags_a_failing_family_and_missing_binary():
    failed = BenchReport(
        families=(_fb("snap_box"), _fb("tube", error="RenderError: boom")),
        environment=environment(),
        binary_present=False,
    )
    md = failed.to_markdown()
    md.encode("cp1252")
    assert not failed.ok
    assert "FAIL" in md
    assert "ERROR: RenderError: boom" in md
    assert "OpenSCAD binary not present" in md


# --- binary-gated: the real deterministic proof -----------------------------------

def _binary_present() -> bool:
    try:
        return Config.load().binary_path("openscad").exists()
    except Exception:
        return False


@pytest.mark.real_tool
@pytest.mark.skipif(not _binary_present(), reason="OpenSCAD binary not fetched")
def test_every_family_re_renders_deterministically_under_budget():
    """The headline Stage 5 proof: every built-in family re-renders through the real
    deterministic pipeline (no model call — a model call would raise) into a watertight mesh
    at its declared envelope, in interactive time. The hard gate is the conservative ceiling
    (RERENDER_CEILING_S) so the suite can't flake; the <1 s target is recorded in the
    committed benchmark doc, not asserted here."""
    report = benchmark_families()
    assert report.binary_present
    # The bench must cover the WHOLE registry (no magic count — the family set is declared
    # once in test_templates.EXPECTED_FAMILY_NAMES and grows with #19).
    assert len(report.families) == len(default_registry().families())
    assert report.ok, [f for f in report.families if not f.ok]
    for f in report.families:
        assert f.error is None, f"{f.name}: {f.error}"
        assert f.rendered and f.watertight, f.name
        assert f.deterministic_emit, f.name
        assert f.bbox_error_mm <= BBOX_TOLERANCE_MM, f"{f.name}: bbox err {f.bbox_error_mm}"
        assert f.rerender_s <= RERENDER_CEILING_S, f"{f.name}: re-render {f.rerender_s:.3f}s"
    # TEST-003 / NEW-001: assert the <1 s interactive headline on REAL renders, but via the
    # MEDIAN family — not every family. A single family can momentarily straddle 1.0 s under load
    # (wall_hook/tube sit ~0.7–1.0 s on the reference box), so a hard per-family <1 s gate would
    # flake; the median (~0.3 s) is jitter-resistant and is the honest "a typical drag re-renders
    # in under a second" claim. RERENDER_CEILING_S above is still the hard per-family correctness
    # gate; the committed proof carries the exact per-family numbers.
    times = sorted(f.rerender_s for f in report.families)
    median = times[len(times) // 2]
    assert median < RERENDER_TARGET_S, (
        f"median re-render {median:.3f}s exceeds the <1 s interactive target; "
        f"per-family: {[(f.name, round(f.rerender_s, 3)) for f in report.families]}"
    )
