"""Stage 8 — a deterministic proof the CadQuery backend produces valid printable geometry.

Mirrors :mod:`kimcad.template_bench` (which proves the OpenSCAD template families): a fixed set
of CadQuery scripts is rendered through the real out-of-process worker and each is checked to be
watertight at its declared envelope. There is NO model in the loop, so the bench is fast and
byte-deterministic — it proves the *engine* is sound (the OCCT export round-trips to a manifold
mesh at the right size), independent of any LLM.

The separate, higher-level claim — that running OpenSCAD and CadQuery as mutual fallbacks lifts
the prompt pass rate ("the union") — needs a LIVE model bench; how to run it is documented in
``docs/benchmarks/stage-8-cadquery-backend.md``. This module is the deterministic floor.

Run it from a test (see ``tests/test_cadquery_bench.py``) or programmatically::

    from kimcad.cadquery_bench import run_cadquery_bench, format_report
    from kimcad.cadquery_runner import find_cadquery_interpreter
    print(format_report(run_cadquery_bench(find_cadquery_interpreter())))
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from kimcad.cadquery_runner import render_cadquery
from kimcad.openscad_runner import RenderError
from kimcad.validation import load_mesh, validate_mesh

# Tessellation + fillet approximation can move a curved envelope by a fraction of a mm; 0.5 mm is
# a comfortable sanity bound that still catches a genuinely wrong-sized part.
BBOX_TOLERANCE_MM = 0.5


@dataclass(frozen=True)
class CadQueryCase:
    """One fixed CadQuery script and the overall envelope it should build, in mm."""

    name: str
    code: str
    expected_bbox_mm: tuple[float, float, float]


# A small, representative spread: a plain solid, a through-hole, a curved solid, a filleted plate,
# and a boolean union (the L-bracket the codegen prompt teaches). Each is a pure cq script that
# assigns ``result`` — the same contract the LLM codegen targets.
CASES: tuple[CadQueryCase, ...] = (
    CadQueryCase("box", 'result = cq.Workplane("XY").box(40, 30, 20)', (40.0, 30.0, 20.0)),
    CadQueryCase(
        "box_with_hole",
        'result = cq.Workplane("XY").box(40, 40, 20).faces(">Z").workplane().hole(8)',
        (40.0, 40.0, 20.0),
    ),
    CadQueryCase("cylinder", 'result = cq.Workplane("XY").cylinder(30, 12)', (24.0, 24.0, 30.0)),
    CadQueryCase(
        "rounded_plate",
        'result = cq.Workplane("XY").box(50, 40, 6).edges("|Z").fillet(5)',
        (50.0, 40.0, 6.0),
    ),
    CadQueryCase(
        "l_bracket",
        (
            'base = cq.Workplane("XY").box(40, 20, 4, centered=(False, True, False))\n'
            'upright = cq.Workplane("XY").box(4, 20, 40, centered=(False, True, False))\n'
            "result = base.union(upright)"
        ),
        (40.0, 20.0, 40.0),
    ),
)


@dataclass
class CaseResult:
    name: str
    rendered: bool
    watertight: bool
    bbox_ok: bool
    bbox_mm: tuple[float, float, float] | None
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.rendered and self.watertight and self.bbox_ok


def _bbox_matches(actual: tuple[float, float, float], expected: tuple[float, float, float]) -> bool:
    # Compare sorted dims so an axis-permutation (a valid orientation) doesn't false-fail.
    return all(
        abs(a - e) <= BBOX_TOLERANCE_MM
        for a, e in zip(sorted(actual), sorted(expected))
    )


def run_cadquery_bench(
    interpreter: Path, out_dir: Path | None = None
) -> list[CaseResult]:
    """Render every case through the real CadQuery worker and report rendered/watertight/bbox.

    ``interpreter`` is a ≤3.13 Python with cadquery (see
    :func:`kimcad.cadquery_runner.find_cadquery_interpreter`); ``out_dir`` defaults to a temp dir.
    """
    tmp = None
    if out_dir is None:
        tmp = tempfile.TemporaryDirectory(prefix="kimcad-cqbench-")
        out_dir = Path(tmp.name)
    try:
        results: list[CaseResult] = []
        for case in CASES:
            try:
                render = render_cadquery(
                    case.code, interpreter=interpreter, out_dir=out_dir, basename=case.name
                )
            except RenderError as e:
                results.append(CaseResult(case.name, False, False, False, None, str(e)))
                continue
            mesh = load_mesh(render.output_path)
            _, report = validate_mesh(mesh)
            bbox = report.bounding_box_mm
            results.append(
                CaseResult(
                    name=case.name,
                    rendered=True,
                    watertight=report.watertight,
                    bbox_ok=_bbox_matches(bbox, case.expected_bbox_mm),
                    bbox_mm=bbox,
                )
            )
        return results
    finally:
        if tmp is not None:
            tmp.cleanup()


def format_report(results: list[CaseResult]) -> str:
    lines = ["CadQuery backend bench - fixed scripts through the real worker", ""]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        bbox = (
            f"{r.bbox_mm[0]:.1f}x{r.bbox_mm[1]:.1f}x{r.bbox_mm[2]:.1f}" if r.bbox_mm else "—"
        )
        detail = r.error or f"watertight={r.watertight} bbox={bbox}"
        lines.append(f"  [{status}] {r.name}: {detail}")
    passed = sum(1 for r in results if r.passed)
    lines.append("")
    lines.append(f"{passed}/{len(results)} cases passed")
    return "\n".join(lines)
