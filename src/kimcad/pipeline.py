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

import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from kimcad.config import Config, Material, Printer
from kimcad.hardening import HardenReport, harden_mesh
from kimcad.ir import DesignPlan, first_clarification
from kimcad.llm_provider import PlanParseError, Provider
from kimcad.openscad_runner import (
    BlockedCodeError,
    RenderError,
    RenderResult,
    render_scad,
)
from kimcad.history import HistoryStore, PrintRecord
from kimcad.orientation import Orientation, auto_orient
from kimcad.printability import Finding, GateResult, Level, dim_tolerance, run_gate
from kimcad.printproof3d import validate_model
from kimcad.smart_mesh import MeshReadiness, assess_readiness
from kimcad.slicer import (
    OrcaProfileError,
    SliceError,
    SliceResult,
    resolve_slice_settings,
    slice_model,
)
from kimcad.templates import TemplateMatch, TemplateRegistry, default_registry
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
    plan_failed = "plan_failed"
    render_failed = "render_failed"
    gate_failed = "gate_failed"
    completed = "completed"


# Shown when the model's response can't be turned into a design plan (bad JSON, or valid
# JSON that doesn't match the schema -- e.g. a too-small model echoing the schema back).
# A clean, actionable message instead of a raw pydantic/JSON traceback.
PLAN_FAILED_MESSAGE = (
    "The model didn't return a usable design plan -- its response couldn't be parsed "
    "into the required structure. This usually means the chosen model is too small or "
    "not suited to structured planning. Try a different model (run `kimcad models` to "
    "see what fits your machine) or rephrase the request."
)

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
    # Pre-slice mesh hardening (Manifold3D); the exported/sliced mesh is the hardened one.
    hardened: bool = False
    harden_summary: str = ""
    # Slice outcome (populated only when a print was confirmed and sliced).
    sliced: bool = False
    gcode_path: str | None = None
    gcode_lines: int | None = None
    gcode_estimate: str | None = None  # slicer print estimate (time / layers / filament)
    slice_note: str | None = None
    # (machine, process, filament) profile names actually used for the slice.
    slice_profiles: tuple[str, str, str] | None = None
    # Stage 7: the Smart Mesh readiness verdict (score / risks / recommendations / confidence),
    # synthesized from the gate + an optional PrintProof3D validation. Always present.
    readiness: MeshReadiness | None = None

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
        if self.harden_summary:
            lines.append(f"Hardening: {self.harden_summary}")
        if self.readiness is not None:
            r = self.readiness
            # ASCII separators on purpose: this report prints to the console, and an ASCII '-'
            # needs no UTF-8 reconfigure to be safe on a legacy code page (defense in depth).
            lines.append(
                f"Readiness: {r.score}/100 - {r.verdict} "
                f"(confidence {r.confidence}; via {r.attribution})"
            )
            for risk in r.risks:
                lines.append(f"  Risk: {risk.title} - {risk.detail}")
            for rec in r.recommendations:
                lines.append(f"  Suggest: {rec}")
            if r.comparison:
                lines.append(f"  History: {r.comparison}")
        if self.sliced:
            detail = f" ({self.gcode_lines} G-code lines)" if self.gcode_lines else ""
            lines.append(f"Slice: G-code produced{detail} -> {self.gcode_path}")
            if self.gcode_estimate:
                lines.append(f"  Estimate: {self.gcode_estimate}")
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
    # The matched template family + its derived parameter values, when the deterministic
    # template engine built this part (None when the LLM-codegen fallback was used). This
    # is what the live-slider UI needs: the typed parameters and the family to re-render.
    template: TemplateMatch | None = None
    extra: dict[str, Any] = field(default_factory=dict)


_FALLBACK_VERDICT = {
    "pass": ("Ready to print", 85),
    "warn": ("Printable with notes", 60),
    "fail": ("Not print-ready", 20),
}


def _fallback_readiness(gate: GateResult) -> MeshReadiness:
    """A last-resort readiness if ``assess_readiness`` itself somehow raised (it shouldn't — it's
    pure over inputs the pipeline already validated). Keeps the build alive with an honest,
    conservative, gate-only card rather than letting an exception escape."""
    tone = str(gate.status) if str(gate.status) in _FALLBACK_VERDICT else "warn"
    verdict, score = _FALLBACK_VERDICT[tone]
    return MeshReadiness(
        score=score,
        verdict=verdict,
        tone=tone,
        confidence="Low",
        attribution="KimCad printability gate",
    )


class Pipeline:
    def __init__(
        self,
        config: Config,
        printer: Printer,
        material: Material,
        provider: Provider,
        *,
        renderer: Renderer | None = None,
        slicer: Slicer | None = None,
        registry: TemplateRegistry | None = None,
        max_render_retries: int = 2,
        history: HistoryStore | None = None,
    ):
        self.config = config
        self.printer = printer
        self.material = material
        self.provider = provider
        self.renderer = renderer or self._default_renderer
        self.slicer = slicer or self._default_slicer
        # The Smart Mesh learning store (Stage 7). Optional: when None (the default, and in unit
        # tests), no history is read or written — the readiness card simply omits the comparison.
        # The CLI/web entrypoints inject a real store so a build is remembered and compared.
        self.history = history
        # The deterministic template engine. Pass an empty TemplateRegistry(()) to force
        # the LLM-codegen path for every part (the engine off); the default registry makes
        # template-covered object types deterministic and instantly re-renderable.
        self.registry = registry if registry is not None else default_registry()
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

        try:
            plan = self.provider.generate_design_plan(
                prompt, self.printer, self.material, history=history
            )
        except PlanParseError as e:
            # The model returned something that isn't a valid design plan. Fail closed with
            # a clean, user-facing message instead of leaking a raw pydantic/JSON traceback.
            # The detail is the underlying parse exception TYPE (enough to categorize the
            # failure); the full multi-line pydantic dump would be noise even on the CLI.
            # Only PlanParseError is caught -- a bug elsewhere propagates, never masked here.
            detail = type(e.original).__name__ if e.original is not None else "PlanParseError"
            return PipelineResult(
                status=PipelineStatus.plan_failed,
                prompt=prompt,
                error=f"{PLAN_FAILED_MESSAGE} (details: {detail})",
            )
        clarification = first_clarification(plan)
        if clarification is not None:
            return PipelineResult(
                status=PipelineStatus.clarification_needed,
                prompt=prompt,
                plan=plan,
                clarification=clarification,
            )

        # Tiered engine: a template-covered object type builds deterministically (no model
        # call, instantly re-renderable); everything else falls back to LLM codegen. For a
        # template part, the size it will actually be is the family's analytic envelope, so
        # align the plan's target bbox to it — the gate then verifies the template built
        # what it declares, and the report/viewport show that size.
        match = self.registry.match(plan)
        if match is not None:
            plan = plan.model_copy(
                update={
                    "bounding_box_mm": list(match.expected_bbox()),
                    # Reflect the template's actual parameter values in the gate plan so
                    # dimension-keyed checks (e.g. wall thickness) gate the geometry that's
                    # built, not the model's original guess.
                    "dimensions": {**plan.dimensions, **match.values},
                }
            )

        render, scad, mesh, mesh_report, gate, attempts, error = self._build_geometry(
            plan, out_dir, basename, gate_retry=not proceed_anyway, match=match
        )
        if render is None:
            return PipelineResult(
                status=PipelineStatus.render_failed,
                prompt=prompt,
                plan=plan,
                scad=scad,
                render_attempts=attempts,
                error=error,
                template=match,
            )

        return self._assemble_result(
            prompt=prompt,
            plan=plan,
            match=match,
            render=render,
            scad=scad,
            mesh=mesh,
            mesh_report=mesh_report,
            gate=gate,
            attempts=attempts,
            out_dir=out_dir,
            basename=basename,
            proceed_anyway=proceed_anyway,
            confirm_print=confirm_print,
        )

    def _assemble_result(
        self,
        *,
        prompt: str,
        plan: DesignPlan,
        match: TemplateMatch | None,
        render: RenderResult,
        scad: str | None,
        mesh: Any,
        mesh_report: MeshReport,
        gate: GateResult,
        attempts: int,
        out_dir: Path,
        basename: str,
        proceed_anyway: bool,
        confirm_print: bool,
        run_engine: bool = True,
        record_history: bool = True,
    ) -> PipelineResult:
        """Shared tail for both a prompt-driven ``run`` and a live-slider ``rerender``:
        orient, harden + export the manifold mesh, build the report, then — on a gate FAIL —
        return without slicing UNLESS the caller passed ``proceed_anyway`` (the explicit
        "slice a failed part for inspection" override; even then a gate-failed part is never
        *sent* to a printer — see the send-gate boundary note in HANDOFF.md / mcp_server.py).
        Keeping this safety sequence — harden-before-export, and the gate-FAIL slice gate — in
        one place means ``run`` and ``rerender`` share exactly one implementation of it."""
        oriented, orientation = auto_orient(mesh)
        # Harden the oriented mesh into a guaranteed manifold before it is exported and
        # sliced; the exported .oriented.stl (also the download fallback) is the hardened
        # mesh, so a clean part goes to the slicer and to the user.
        hardened, harden_report = harden_mesh(oriented)
        mesh_path = out_dir / f"{basename}.oriented.stl"
        hardened.export(str(mesh_path))

        report = self._build_report(plan, render, mesh_report, gate, orientation, harden_report)

        # ENG-001: the exported/sliced mesh is the hardened one. If hardening actually
        # altered the geometry, re-derive the report's integrity facts from the hardened
        # mesh so the report describes the artifact that ships, not the pre-harden input.
        if harden_report.ok and harden_report.changed:
            _, hardened_mr = validate_mesh(hardened)
            report.watertight = hardened_mr.watertight
            report.volume_mm3 = hardened_mr.volume_mm3
            report.n_bodies = hardened_mr.n_bodies

        # Stage 7: the Smart Mesh readiness verdict, on the report so both the gate-failed and
        # completed paths carry it. Computed on the FINAL hardened mesh (the artifact that ships),
        # using PrintProof3D's deeper validation when the engine is configured, else the gate
        # alone. The live-slider rerender passes run_engine=False so a drag stays snappy.
        report.readiness = self._compute_readiness(
            gate, mesh_report, hardened, run_engine=run_engine
        )
        # The learning layer runs on a fresh design only, not a live-slider drag: fold in the
        # "compared to your past parts" line (ranked against PRIOR records), THEN record this
        # build. A drag would otherwise flood the store and rank a part against its own parent.
        if record_history:
            self._apply_history_comparison(report.readiness, plan)
            self._record_history(plan, report)

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
                template=match,
            )

        slice_result = None
        slice_error = None
        if confirm_print:
            try:
                slice_result = self.slicer(mesh_path, out_dir, basename)
            except OrcaProfileError as e:
                # A profile gap, not an operational failure: either the printer has no process
                # profile, or this material isn't available on it. The wrapped message names
                # which; don't pre-judge it as a printer-only gap.
                slice_error = f"not sliceable as configured: {e}"
            except SliceError as e:
                # An operational failure on a sliceable printer (bad slice / timeout).
                slice_error = f"slicing failed: {e}"
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
            template=match,
        )

    def _compute_readiness(
        self, gate: GateResult, mesh_report: MeshReport, hardened: Any, *, run_engine: bool = True
    ) -> MeshReadiness:
        """Synthesize the Smart Mesh readiness for the hardened (final) mesh. Runs the deeper
        PrintProof3D validation when the engine is configured, else falls back to the gate alone.
        The mesh is **bed-positioned** (min-corner -> bed origin) before validation, because
        PrintProof3D measures extents from ``[0, build]`` and a centered part would false-flag
        out-of-bounds. Best-effort: a failure to run PrintProof3D never breaks the pipeline.

        ``run_engine=False`` skips the engine subprocess entirely and computes the instant
        gate-only verdict — used on the live-slider ``rerender`` hot path so a debounced drag
        never blocks on a deep-validation subprocess (the engine validates once on the initial
        design instead). The gate-only readiness is honestly attributed, so the card stays
        consistent across a drag."""
        printproof = None
        binary = self.config.printproof3d_binary()
        if binary is not None and run_engine:
            try:
                bed = hardened.copy()
                bed.apply_translation(-bed.bounds[0])  # min-corner -> (0, 0, 0)
                with tempfile.TemporaryDirectory(prefix="kimcad-pp3d-mesh-") as td:
                    stl = Path(td) / "bed.stl"
                    bed.export(str(stl))
                    printproof = validate_model(
                        str(stl), self.printer, self.material, binary=binary
                    )
            except Exception:  # noqa: BLE001 - readiness must never break the build
                printproof = None
        try:
            return assess_readiness(
                gate, mesh_report, material_name=self.material.name, printproof=printproof
            )
        except Exception:  # noqa: BLE001 - assess_readiness is pure over validated inputs, but the
            # never-breaks-the-build contract is airtight: a last-resort gate-only card, not a raise.
            return _fallback_readiness(gate)

    def _apply_history_comparison(self, readiness: MeshReadiness, plan: DesignPlan) -> None:
        """Fold an honest "compared to your past parts" line (and a history attribution) into the
        readiness, comparing this part's score against the PRIOR records. Best-effort: a store
        read failure leaves the readiness untouched (no comparison) rather than breaking the build."""
        if self.history is None:
            return
        try:
            line = self.history.comparison(
                object_type=plan.object_type, score=readiness.score
            )
        except Exception:  # noqa: BLE001 - the learning line is never load-bearing
            line = None
        if line is not None:
            readiness.comparison = line
            readiness.attribution = f"{readiness.attribution} and your local build history"
            readiness.sources.append("build-history")

    def _record_history(self, plan: DesignPlan, report: PrintReport) -> None:
        """Append this build to the learning store. Best-effort: any failure is swallowed so a
        logging miss never breaks a build. Stores a coarse record (type, readiness score, gate,
        material, largest dimension) — no geometry, no prompt."""
        if self.history is None or report.readiness is None:
            return
        try:
            max_dim = max(report.actual_bbox_mm) if report.actual_bbox_mm else 0.0
            self.history.record(
                PrintRecord(
                    object_type=plan.object_type,
                    score=report.readiness.score,
                    gate_status=report.gate_status,
                    material=self.material.name,
                    max_dim_mm=float(max_dim),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        except Exception:  # noqa: BLE001 - history is never load-bearing
            return

    def rerender(
        self,
        base_plan: DesignPlan,
        family_name: str,
        values: dict[str, float],
        out_dir: Path,
        *,
        basename: str = "part",
        proceed_anyway: bool = False,
        confirm_print: bool = False,
    ) -> PipelineResult:
        """Deterministically re-render a template-backed part at new parameter values — the
        live-slider path. No model call and no prompt: rebuild the match from the family +
        (clamped) values, re-align the target envelope, and run the same single-shot build +
        gate + assemble tail as a template ``run``. ``base_plan`` carries the unchanged
        object_type / summary / printer / material so the report and gate behave exactly as
        on the original design. An unknown family is reported as ``render_failed`` (the
        caller passed a family that isn't in the registry)."""
        out_dir.mkdir(parents=True, exist_ok=True)
        match = self.registry.match_family(family_name, values)
        if match is None:
            return PipelineResult(
                status=PipelineStatus.render_failed,
                prompt="",
                plan=base_plan,
                error=f"unknown template family '{family_name}'",
            )
        plan = base_plan.model_copy(
            update={
                "bounding_box_mm": list(match.expected_bbox()),
                # The slider values are the part's current dimensions — gate against them, not
                # the original design's, so dragging the wall thin actually warns.
                "dimensions": {**base_plan.dimensions, **match.values},
            }
        )
        render, scad, mesh, mesh_report, gate, attempts, error = self._build_from_template(
            match, plan, out_dir, basename
        )
        if render is None:
            return PipelineResult(
                status=PipelineStatus.render_failed,
                prompt="",
                plan=plan,
                scad=scad,
                render_attempts=attempts,
                error=error,
                template=match,
            )
        return self._assemble_result(
            prompt="",
            plan=plan,
            match=match,
            render=render,
            scad=scad,
            mesh=mesh,
            mesh_report=mesh_report,
            gate=gate,
            attempts=attempts,
            out_dir=out_dir,
            basename=basename,
            proceed_anyway=proceed_anyway,
            confirm_print=confirm_print,
            # Live-slider hot path: skip the engine subprocess so a debounced drag stays snappy;
            # the gate-only readiness is computed instantly and honestly attributed. Don't record
            # to history either — a drag isn't a new design, and would flood the store.
            run_engine=False,
            record_history=False,
        )

    @staticmethod
    def _record_slice(
        report: PrintReport, slice_result: Any, slice_error: str | None
    ) -> None:
        """Fold the slice outcome into the print report. A refusal (no process profile,
        etc.) is recorded as a note, not an exception — the validated mesh is still
        exported, so the user can fall back to a plain mesh download."""
        if slice_error is not None:
            report.slice_note = slice_error  # already categorized by run()
            return
        if isinstance(slice_result, SliceResult):
            report.sliced = True
            report.gcode_path = str(slice_result.gcode_path)
            if slice_result.gcode_proof is not None:
                report.gcode_lines = slice_result.gcode_proof.line_count
                report.gcode_estimate = slice_result.gcode_proof.estimate_summary() or None
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
        match: TemplateMatch | None = None,
    ) -> tuple[
        RenderResult | None,
        str | None,
        Any,
        MeshReport | None,
        GateResult | None,
        int,
        str | None,
    ]:
        """Produce geometry for the plan: the deterministic template path when a family
        matched, else generate OpenSCAD with the model and run the render+Gate feedback
        loop.

        LLM path — two classes of failure are fed back to the model and retried within a
        single attempt budget, then the loop fails closed:
        - render / blocked-code errors (the code produced no geometry);
        - fixable Gate failures (it rendered, but the size is wrong or it doesn't fit
          the build volume) — only when ``gate_retry`` is set, since ``proceed_anyway``
          means the caller has already chosen to accept the gate result.

        Returns (render, scad, mesh, mesh_report, gate, attempts, error). ``render`` is
        None only when geometry never rendered (caller maps that to render_failed).
        """
        if match is not None:
            return self._build_from_template(match, plan, out_dir, basename)

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

    def _build_from_template(
        self,
        match: TemplateMatch,
        plan: DesignPlan,
        out_dir: Path,
        basename: str,
    ) -> tuple[
        RenderResult | None,
        str | None,
        Any,
        MeshReport | None,
        GateResult | None,
        int,
        str | None,
    ]:
        """The deterministic path: emit the template's OpenSCAD (a pure function of its
        in-range parameters — no model call), render once, and run the Gate against the
        template's declared envelope.

        No feedback loop: re-rendering identical SCAD can't change the outcome, so a
        render/blocked error is surfaced directly rather than retried, and a part that
        fails the Gate (e.g. too big for the build volume) fails closed — the fix is to
        adjust a parameter (a live-slider re-render), not to regenerate geometry. Returns
        the same 7-tuple as the LLM path with ``attempts`` fixed at 1.
        """
        scad = match.scad()
        try:
            render = self.renderer(scad, out_dir, basename)
        except (RenderError, BlockedCodeError) as e:
            # A proven library module shouldn't fail to render; surface it as a real defect
            # rather than mask it with an LLM fallback (no-match is the only fallback path).
            return None, scad, None, None, None, 1, str(e)

        mesh = load_mesh(render.output_path)
        mesh, mesh_report = validate_mesh(mesh)
        gate = run_gate(mesh_report, plan, self.printer, self.material)
        return render, scad, mesh, mesh_report, gate, 1, None

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
        harden_report: HardenReport | None = None,
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
            hardened=bool(harden_report and harden_report.ok),
            harden_summary=harden_report.summary() if harden_report else "",
        )
