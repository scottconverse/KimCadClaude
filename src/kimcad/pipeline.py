"""Pipeline orchestrator + print report (spec §6, §5.2).

Wires the deterministic spine end to end:

    prompt → design plan → [clarify?] → OpenSCAD → render → validate →
    Printability Gate → auto-orient → [confirm + slice?] → print report

The LLM provider, the renderer, and the slicer are all injected so the whole
orchestration — including the render-retry loop and the Gate escape hatch — is
testable offline against real Trimesh geometry, with no binary or network.

Two safety behaviors from the threat model (§12) live here, not in the leaf stages:
- un-renderable / blocked codegen is fed back to the model and retried, then fails
  closed rather than looping forever;
- G-code is only produced after explicit printer confirmation (``confirm_print``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from kimcad.config import Config, Material, Printer
from kimcad.ir import DesignPlan, first_clarification
from kimcad.llm_provider import LLMProvider
from kimcad.openscad_runner import (
    BlockedCodeError,
    RenderError,
    RenderResult,
    render_scad,
)
from kimcad.orientation import Orientation, auto_orient
from kimcad.printability import Finding, GateResult, Level, dim_tolerance, run_gate
from kimcad.slicer import SliceError, SliceResult, resolve_slice_settings, slice_model
from kimcad.validation import MeshReport, load_mesh, validate_mesh

Renderer = Callable[[str, Path, str], RenderResult]
Slicer = Callable[[Path, Path, str], Any]

# Gate failures the model can plausibly fix by regenerating geometry. A thin wall or
# stray-shell WARN doesn't FAIL the gate; these two are the only FAIL codes, and both
# are codegen mistakes (wrong size, doesn't fit) rather than dead ends.
_RETRY_GATE_CODES = frozenset({"dim.mismatch", "volume.exceeds", "mesh.not_watertight"})


def _fixable_gate_failures(gate: GateResult) -> list[Finding]:
    return [f for f in gate.findings if f.level is Level.FAIL and f.code in _RETRY_GATE_CODES]


def _render_feedback(error: str) -> str:
    return (
        "The previous OpenSCAD failed to render with this error:\n"
        f"{error}\n"
        "Return corrected OpenSCAD only — no prose, no code fences."
    )


def _axis_breakdown(plan: DesignPlan, report: MeshReport | None) -> str:
    """Per-axis target-vs-built table so the model sees every wrong axis at once.

    The gate's finding message only names the single worst axis; a part with two
    wrong axes would otherwise learn about them one retry at a time and run out of
    budget before converging. Spelling out all three axes makes the fix one-shot.
    """
    if plan.bounding_box_mm is None or report is None:
        return ""
    exp = plan.bounding_box_mm
    got = report.bounding_box_mm
    lines = []
    for axis, e, g in zip("XYZ", exp, got):
        if abs(g - e) <= dim_tolerance(e):
            lines.append(f"  {axis}: {g:.1f} mm — ok")
        elif g > e:
            lines.append(f"  {axis}: {g:.1f} mm — too big, target {e:.1f} mm")
        else:
            lines.append(f"  {axis}: {g:.1f} mm — too small, target {e:.1f} mm")
    return (
        f"Target envelope: {exp[0]:.1f} x {exp[1]:.1f} x {exp[2]:.1f} mm.\n"
        f"You built: {got[0]:.1f} x {got[1]:.1f} x {got[2]:.1f} mm.\n" + "\n".join(lines) + "\n"
    )


def _gate_feedback(findings: list[Finding], plan: DesignPlan, report: MeshReport | None) -> str:
    issues = "\n".join(f"- {f.message}" for f in findings)
    return (
        "The previous OpenSCAD rendered, but the part failed the printability gate:\n"
        f"{issues}\n"
        f"{_axis_breakdown(plan, report)}"
        "Fix the geometry so the finished part's overall size matches the design "
        "plan's bounding box on every axis (X, Y, Z) — map each named dimension to "
        "the correct axis and cut through-holes fully through the part. Return "
        "corrected OpenSCAD only — no prose, no code fences."
    )


class PipelineStatus(str, Enum):
    clarification_needed = "clarification_needed"
    render_failed = "render_failed"
    gate_failed = "gate_failed"
    completed = "completed"


@dataclass
class PrintReport:
    object_type: str
    summary: str
    printer: str
    material: str
    gate_status: str
    headline: str
    target_bbox_mm: list[float] | None
    actual_bbox_mm: tuple[float, float, float]
    findings: list[tuple[str, str, str]]
    watertight: bool
    repaired: bool
    repairs: list[str]
    n_bodies: int
    volume_mm3: float
    orientation: str
    orientation_stability: float
    sanitizer_removed: list[str]
    # Slice outcome (populated only when a print was confirmed and sliced).
    sliced: bool = False
    gcode_path: str | None = None
    gcode_lines: int | None = None
    slice_note: str | None = None
    # (machine, process, filament) profile names actually used for the slice.
    slice_profiles: tuple[str, str, str] | None = None

    def to_text(self) -> str:
        ax, ay, az = self.actual_bbox_mm
        lines = [
            f"{self.object_type} — {self.summary}",
            f"Printer: {self.printer}   Material: {self.material}",
            f"Gate: {self.gate_status.upper()}",
            f"Headline: {self.headline}" if self.headline else "",
            f"Size: {ax:.1f} × {ay:.1f} × {az:.1f} mm"
            + (
                f" (target {self.target_bbox_mm[0]:.1f} × "
                f"{self.target_bbox_mm[1]:.1f} × {self.target_bbox_mm[2]:.1f})"
                if self.target_bbox_mm
                else ""
            ),
            f"Mesh: {'watertight' if self.watertight else 'NOT watertight'}, "
            f"{self.n_bodies} body(ies), volume {self.volume_mm3:.0f} mm³"
            + (f" (repaired: {'; '.join(self.repairs)})" if self.repaired else ""),
            f"Orientation: {self.orientation} (stability {self.orientation_stability:.2f})",
        ]
        if self.sliced:
            detail = f" ({self.gcode_lines} G-code lines)" if self.gcode_lines else ""
            lines.append(f"Slice: G-code produced{detail} -> {self.gcode_path}")
            if self.slice_profiles:
                machine, process, filament = self.slice_profiles
                lines.append(
                    f"  Profiles: machine={machine} | process={process} | "
                    f"filament={filament}"
                )
        elif self.slice_note:
            lines.append(f"Slice: {self.slice_note}")
        for level, code, message in self.findings:
            lines.append(f"  [{level}] {code}: {message}")
        if self.sanitizer_removed:
            lines.append("Sanitizer removed:")
            lines.extend(f"  - {r}" for r in self.sanitizer_removed)
        return "\n".join(ln for ln in lines if ln)


@dataclass
class PipelineResult:
    status: PipelineStatus
    prompt: str
    plan: DesignPlan | None = None
    clarification: str | None = None
    scad: str | None = None
    render: RenderResult | None = None
    mesh_report: MeshReport | None = None
    gate: GateResult | None = None
    orientation: Orientation | None = None
    mesh_path: Path | None = None
    report: PrintReport | None = None
    slice_result: Any = None
    slice_error: str | None = None
    error: str | None = None
    render_attempts: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


class Pipeline:
    def __init__(
        self,
        config: Config,
        printer: Printer,
        material: Material,
        provider: LLMProvider,
        *,
        renderer: Renderer | None = None,
        slicer: Slicer | None = None,
        max_render_retries: int = 2,
    ):
        self.config = config
        self.printer = printer
        self.material = material
        self.provider = provider
        self.renderer = renderer or self._default_renderer
        self.slicer = slicer or self._default_slicer
        self.max_render_retries = max_render_retries

    def _default_renderer(self, scad: str, out_dir: Path, basename: str) -> RenderResult:
        return render_scad(
            scad,
            binary=self.config.binary_path("openscad"),
            out_dir=out_dir,
            basename=basename,
            output_format=self.config.default_output_format(),
            timeout_s=self.config.limit("openscad_timeout_simple_s"),
            max_output_bytes=self.config.limit("max_output_bytes"),
        )

    def _default_slicer(self, mesh_path: Path, out_dir: Path, basename: str) -> SliceResult:
        """Resolve the configured printer + material to on-disk OrcaSlicer profiles and
        slice the oriented mesh into a G-code-bearing 3MF. Raises :class:`SliceError`
        (e.g. when the printer has no process profile); ``run`` catches that and reports
        slicing as unavailable rather than failing the whole job."""
        settings = resolve_slice_settings(
            self.config.orca_profiles_root(), self.printer, self.material
        )
        return slice_model(
            mesh_path,
            binary=self.config.binary_path("orcaslicer"),
            out_dir=out_dir,
            settings=settings,
            basename=basename,
            timeout_s=self.config.limit("slice_timeout_s"),
        )

    def run(
        self,
        prompt: str,
        out_dir: Path,
        *,
        history: list[dict[str, str]] | None = None,
        proceed_anyway: bool = False,
        confirm_print: bool = False,
        basename: str = "part",
    ) -> PipelineResult:
        out_dir.mkdir(parents=True, exist_ok=True)

        plan = self.provider.generate_design_plan(
            prompt, self.printer, self.material, history=history
        )
        clarification = first_clarification(plan)
        if clarification is not None:
            return PipelineResult(
                status=PipelineStatus.clarification_needed,
                prompt=prompt,
                plan=plan,
                clarification=clarification,
            )

        render, scad, mesh, mesh_report, gate, attempts, error = self._build_geometry(
            plan, out_dir, basename, gate_retry=not proceed_anyway
        )
        if render is None:
            return PipelineResult(
                status=PipelineStatus.render_failed,
                prompt=prompt,
                plan=plan,
                scad=scad,
                render_attempts=attempts,
                error=error,
            )

        oriented, orientation = auto_orient(mesh)
        mesh_path = out_dir / f"{basename}.oriented.stl"
        oriented.export(str(mesh_path))

        report = self._build_report(plan, render, mesh_report, gate, orientation)

        if gate.status is Level.FAIL and not proceed_anyway:
            return PipelineResult(
                status=PipelineStatus.gate_failed,
                prompt=prompt,
                plan=plan,
                scad=scad,
                render=render,
                mesh_report=mesh_report,
                gate=gate,
                orientation=orientation,
                mesh_path=mesh_path,
                report=report,
                render_attempts=attempts,
            )

        slice_result = None
        slice_error = None
        if confirm_print and self.slicer is not None:
            try:
                slice_result = self.slicer(mesh_path, out_dir, basename)
            except SliceError as e:
                slice_error = str(e)
            self._record_slice(report, slice_result, slice_error)

        return PipelineResult(
            status=PipelineStatus.completed,
            prompt=prompt,
            plan=plan,
            scad=scad,
            render=render,
            mesh_report=mesh_report,
            gate=gate,
            orientation=orientation,
            mesh_path=mesh_path,
            report=report,
            slice_result=slice_result,
            slice_error=slice_error,
            render_attempts=attempts,
        )

    @staticmethod
    def _record_slice(
        report: PrintReport, slice_result: Any, slice_error: str | None
    ) -> None:
        """Fold the slice outcome into the print report. A refusal (no process profile,
        etc.) is recorded as a note, not an exception — the validated mesh is still
        exported, so the user can fall back to a plain mesh download."""
        if slice_error is not None:
            report.slice_note = f"slicing unavailable: {slice_error}"
            return
        if isinstance(slice_result, SliceResult):
            report.sliced = True
            report.gcode_path = str(slice_result.gcode_path)
            if slice_result.gcode_proof is not None:
                report.gcode_lines = slice_result.gcode_proof.line_count
            if slice_result.settings is not None:
                s = slice_result.settings
                report.slice_profiles = (s.machine.stem, s.process.stem, s.filament.stem)

    def _build_geometry(
        self,
        plan: DesignPlan,
        out_dir: Path,
        basename: str,
        *,
        gate_retry: bool = True,
    ) -> tuple[
        RenderResult | None,
        str | None,
        Any,
        MeshReport | None,
        GateResult | None,
        int,
        str | None,
    ]:
        """Generate OpenSCAD, render, and run the Gate in one feedback loop.

        Two classes of failure are fed back to the model and retried within a single
        attempt budget, then the loop fails closed:
        - render / blocked-code errors (the code produced no geometry);
        - fixable Gate failures (it rendered, but the size is wrong or it doesn't fit
          the build volume) — only when ``gate_retry`` is set, since ``proceed_anyway``
          means the caller has already chosen to accept the gate result.

        Returns (render, scad, mesh, mesh_report, gate, attempts, error). ``render`` is
        None only when geometry never rendered (caller maps that to render_failed).
        """
        thread: list[dict[str, str]] = []
        scad = self.provider.generate_openscad(plan, self.printer, self.material, history=thread)
        last_error: str | None = None
        render: RenderResult | None = None
        mesh: Any = None
        mesh_report: MeshReport | None = None
        gate: GateResult | None = None

        for attempt in range(1, self.max_render_retries + 2):
            try:
                render = self.renderer(scad, out_dir, basename)
            except (RenderError, BlockedCodeError) as e:
                last_error = str(e)
                if attempt > self.max_render_retries:
                    return None, scad, None, None, None, attempt, last_error
                self._feed_back(thread, scad, _render_feedback(last_error))
                scad = self.provider.generate_openscad(
                    plan, self.printer, self.material, history=thread
                )
                continue

            mesh = load_mesh(render.output_path)
            mesh, mesh_report = validate_mesh(mesh)
            gate = run_gate(mesh_report, plan, self.printer, self.material)

            fixable = _fixable_gate_failures(gate) if gate_retry else []
            if fixable and attempt <= self.max_render_retries:
                self._feed_back(thread, scad, _gate_feedback(fixable, plan, mesh_report))
                scad = self.provider.generate_openscad(
                    plan, self.printer, self.material, history=thread
                )
                continue

            return render, scad, mesh, mesh_report, gate, attempt, None

        return render, scad, mesh, mesh_report, gate, self.max_render_retries + 1, None

    @staticmethod
    def _feed_back(thread: list[dict[str, str]], scad: str, message: str) -> None:
        thread.append({"role": "assistant", "content": scad})
        thread.append({"role": "user", "content": message})

    def _build_report(
        self,
        plan: DesignPlan,
        render: RenderResult,
        mesh_report: MeshReport,
        gate: GateResult,
        orientation: Orientation,
    ) -> PrintReport:
        headline = next((f.message for f in gate.findings if f.code.startswith("dim.")), "")
        return PrintReport(
            object_type=plan.object_type,
            summary=plan.summary,
            printer=self.printer.name,
            material=self.material.name,
            gate_status=str(gate.status),
            headline=headline,
            target_bbox_mm=plan.bounding_box_mm,
            actual_bbox_mm=mesh_report.bounding_box_mm,
            findings=[(str(f.level), f.code, f.message) for f in gate.findings],
            watertight=mesh_report.watertight,
            repaired=mesh_report.repaired,
            repairs=mesh_report.repairs,
            n_bodies=mesh_report.n_bodies,
            volume_mm3=mesh_report.volume_mm3,
            orientation=orientation.description,
            orientation_stability=orientation.stability,
            sanitizer_removed=render.sanitize.removed,
        )
