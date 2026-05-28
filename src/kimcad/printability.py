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

from dataclasses import dataclass, field
from enum import IntEnum

from kimcad.config import Material, Printer
from kimcad.ir import DesignPlan
from kimcad.validation import MeshReport

# Keys in DesignPlan.dimensions that we treat as a wall thickness.
_WALL_KEYS = ("wall", "wall_thickness", "wall_mm", "thickness")


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
    dim_tol_mm: float = 0.5,
    dim_tol_frac: float = 0.02,
) -> GateResult:
    result = GateResult()

    _check_dimensions(result, report, plan, dim_tol_mm, dim_tol_frac)
    _check_build_volume(result, report, printer)
    _check_wall_thickness(result, plan, printer, material)
    _check_shells(result, report)

    if not result.findings:
        result.add(Level.PASS, "ok", "All Phase-1 printability checks passed.")
    return result


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
    if report.n_bodies > 1:
        result.add(
            Level.WARN,
            "shells.multiple",
            f"{report.n_bodies} disconnected bodies — usually a stray-geometry mistake.",
        )
