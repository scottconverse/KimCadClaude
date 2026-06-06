"""The Printability Gate (spec §6.6).

"Watertight" answers "is this a closed solid?" Users mean "will this print well on
*my* printer in *my* material?" The Gate sits between mesh validation and slicing and
emits pass / warn / fail with reasons, plus a "proceed anyway" escape hatch.

Phase-1 check set (start simple, expand in Phase 3):
- Dimensional assertion — rendered bbox vs the design-plan envelope. The headline.
- Bounding box vs build volume — must fit the selected printer.
- Minimum wall thickness — declared wall vs material/nozzle minimum.
- Disconnected shells — stray bodies are usually a mistake.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum

from kimcad.config import Material, Printer
from kimcad.ir import DesignPlan
from kimcad.validation import MeshReport

# Keys in DesignPlan.dimensions that we treat as a wall thickness.
_WALL_KEYS = ("wall", "wall_thickness", "wall_mm", "thickness")

# Dimensional-fidelity tolerance for the rendered envelope vs the plan. Single source
# of truth so the gate and the retry feedback can never disagree. The mesh is exact,
# deterministic geometry (print-time shrinkage is not in play here), so a correctly
# built part should match its stated envelope to well under a millimetre. The bar is a
# flat 0.5 mm — enough to absorb a fillet/chamfer or mesh-export noise, but no relative
# term: a percentage would let large parts drift (2% of 200 mm = 4 mm) and "pass" a part
# that won't fit. (Decision: Scott, 2026-05-29 — accuracy over leniency.)
DIM_TOL_MM = 0.5
DIM_TOL_FRAC = 0.0


def dim_tolerance(expected_mm: float) -> float:
    """Allowed deviation on one axis: a flat floor (no relative term — see above)."""
    return max(DIM_TOL_MM, expected_mm * DIM_TOL_FRAC)


class Level(IntEnum):
    PASS = 0
    WARN = 1
    FAIL = 2

    def __str__(self) -> str:
        return self.name.lower()


@dataclass
class Finding:
    level: Level
    code: str
    message: str


@dataclass
class GateResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def status(self) -> Level:
        return max((f.level for f in self.findings), default=Level.PASS)

    @property
    def failed(self) -> bool:
        return self.status is Level.FAIL

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.level is Level.FAIL]

    def add(self, level: Level, code: str, message: str) -> None:
        self.findings.append(Finding(level, code, message))


def run_gate(
    report: MeshReport,
    plan: DesignPlan,
    printer: Printer,
    material: Material,
    *,
    dim_tol_mm: float = DIM_TOL_MM,
    dim_tol_frac: float = DIM_TOL_FRAC,
) -> GateResult:
    result = GateResult()

    _check_finite_extents(result, report)
    _check_integrity(result, report)
    _check_dimensions(result, report, plan, dim_tol_mm, dim_tol_frac)
    _check_build_volume(result, report, printer)
    _check_wall_thickness(result, plan, printer, material)
    _check_shells(result, report)

    if not result.findings:
        result.add(Level.PASS, "ok", "All Phase-1 printability checks passed.")
    return result


def _check_finite_extents(result: GateResult, report: MeshReport) -> None:
    """ENG-001: a degenerate mesh can produce NaN/inf bounding-box extents. Because IEEE NaN
    compares False against every threshold, a non-finite bbox would otherwise SILENTLY PASS the
    dimension and build-volume checks — a part that can't be measured must never read as printable.
    Fail closed, first, so the later numeric checks never see a non-finite value."""
    if not all(math.isfinite(v) for v in report.bounding_box_mm):
        result.add(
            Level.FAIL,
            "dim.non_finite",
            "The part's measured size is not a finite number (degenerate or broken geometry) — "
            "it can't be verified or printed. Rebuild the part.",
        )


def _check_integrity(result: GateResult, report: MeshReport) -> None:
    """A part that isn't a closed, watertight solid is not printable — full stop.

    The mesh validator already detects this; the gate must act on it, or a leaky /
    non-manifold mesh that happens to match its dimensions would pass as a valid print
    job. A mesh that needed repair to become watertight had a real defect, so it is
    surfaced as a warning even when the repair succeeded.
    """
    if not report.watertight:
        detail = f" ({'; '.join(report.errors)})" if report.errors else ""
        result.add(
            Level.FAIL,
            "mesh.not_watertight",
            "Mesh is not a closed, watertight solid — it cannot be printed reliably"
            f"{detail}. Rebuild the geometry as a single manifold solid (overlap unions, "
            "cut tools through the surface).",
        )
    elif report.repaired:
        result.add(
            Level.WARN,
            "mesh.repaired",
            f"Mesh was not watertight as generated and had to be repaired "
            f"({'; '.join(report.repairs)}); prefer geometry that is manifold without repair.",
        )
    else:
        result.add(Level.PASS, "mesh.solid", "Closed, watertight solid.")


def _check_dimensions(
    result: GateResult,
    report: MeshReport,
    plan: DesignPlan,
    tol_mm: float,
    tol_frac: float,
) -> None:
    expected = plan.bounding_box_mm
    if expected is None:
        result.add(
            Level.WARN,
            "dim.no_target",
            "No stated envelope in the design plan; cannot assert dimensions.",
        )
        return
    got = report.bounding_box_mm
    worst: tuple[str, float, float, float] | None = None
    for axis, e, g in zip("XYZ", expected, got):
        tol = max(tol_mm, e * tol_frac)
        delta = abs(g - e)
        if delta > tol and (worst is None or delta > worst[3]):
            worst = (axis, e, g, delta)
    if worst is None:
        result.add(
            Level.PASS,
            "dim.match",
            f"Dimensions match: {got[0]:.1f} × {got[1]:.1f} × {got[2]:.1f} mm.",
        )
    else:
        axis, e, g, _ = worst
        result.add(
            Level.FAIL,
            "dim.mismatch",
            f"{axis} is {g:.1f} mm but the spec asked for {e:.1f} mm "
            f"(got {got[0]:.1f} × {got[1]:.1f} × {got[2]:.1f} mm).",
        )


def _check_build_volume(result: GateResult, report: MeshReport, printer: Printer) -> None:
    if printer.build_volume is None:
        result.add(
            Level.WARN,
            "volume.unchecked",
            f"Build volume for {printer.name} is unknown (not configured / not reported "
            "by the printer), so build-plate fit was not checked.",
        )
        return
    over = [
        f"{axis} {g:.1f} > {b:.0f}"
        for axis, g, b in zip("XYZ", report.bounding_box_mm, printer.build_volume)
        if g > b
    ]
    if over:
        result.add(
            Level.FAIL,
            "volume.exceeds",
            f"Part exceeds the {printer.name} build volume ({', '.join(over)} mm). "
            "Scale it down or split it before slicing.",
        )
    else:
        result.add(Level.PASS, "volume.fits", f"Fits the {printer.name} build plate.")


def _check_wall_thickness(
    result: GateResult,
    plan: DesignPlan,
    printer: Printer,
    material: Material,
) -> None:
    declared = next(
        (plan.dimensions[k] for k in _WALL_KEYS if k in plan.dimensions),
        None,
    )
    if declared is None:
        return  # no declared wall to check; mesh-measured thickness is Phase 3
    if printer.nozzle_diameter is None:
        return  # nozzle unknown -> can't compute the minimum wall; skip quietly
    minimum = material.min_wall_mm(printer.nozzle_diameter)
    if declared < minimum:
        result.add(
            Level.WARN,
            "wall.thin",
            f"Wall is {declared:.1f} mm, below the {minimum:.1f} mm recommended for "
            f"{material.name} on a {printer.nozzle_diameter:.1f} mm nozzle.",
        )
    else:
        result.add(Level.PASS, "wall.ok", f"Wall {declared:.1f} mm is adequate.")


def _check_shells(result: GateResult, report: MeshReport) -> None:
    """Warn only on genuinely *stray* bodies, not on plain hollow containers.

    A fully-sealed hollow container (a box with walls) is one watertight solid, but
    trimesh counts its outer skin and inner cavity skin as two separate bodies, so
    ``n_bodies == 2`` for correct, intended geometry (the demo snap_box trips this).
    The validator distinguishes a nested cavity (contained bbox) from a stray body
    (disjoint bbox) and reports the stray count, so we key the warning off
    ``stray_bodies`` — a hollow container has ``stray_bodies == 0`` and must not warn,
    while loose extra geometry has ``stray_bodies >= 1`` and should.
    """
    if report.stray_bodies > 0:
        bodies = report.stray_bodies + 1  # strays plus the main body
        result.add(
            Level.WARN,
            "shells.multiple",
            f"{bodies} disconnected bodies ({report.stray_bodies} stray, sitting apart "
            "from the main body) — usually a stray-geometry mistake.",
        )
