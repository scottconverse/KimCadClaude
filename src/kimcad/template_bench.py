"""Stage 5 — deterministic-template benchmark / proof.

Proves the headline Stage 5 promise for every built-in template family: changing a
parameter re-renders the part LOCALLY and DETERMINISTICALLY — no prompt, no model call —
fast enough to drive a live slider, and the rendered mesh matches the family's analytic
envelope.

This is the deterministic counterpart to :mod:`kimcad.benchmark` (which scores the LLM
prompt->design success rate). Here there is no prompt and the provider is never called:
"no model" is *structural* (``Pipeline.rerender`` runs a pure emit + render), and a
:class:`_NoModelProvider` makes it a *runtime* guarantee too — any accidental model call
raises rather than silently invoking an LLM. It times the same ``Pipeline.rerender`` path
the web ``POST /api/render`` endpoint runs (emit -> OpenSCAD -> validate -> orient ->
harden -> export), so the reported number is the real user-facing re-render cost.

Run it as a tool: ``python -m kimcad.template_bench [--write PATH]``. Needs the OpenSCAD
binary (the same one the pipeline uses); without it, rendering can't happen and the run
reports that plainly.
"""

from __future__ import annotations

import argparse
import platform
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from kimcad.config import Config
from kimcad.ir import DesignPlan
from kimcad.pipeline import Pipeline, PipelineStatus
from kimcad.templates import (
    TemplateFamily,
    TemplateRegistry,
    clamp_values,
    default_registry,
    emit_scad,
)

# The interactive target for a slider re-render (the spec's "<1 s, no round-trip" headline).
# Reported per family, but NOT the hard automated gate — that's RERENDER_CEILING_S, below.
RERENDER_TARGET_S = 1.0
# A conservative, hardware-independent ceiling the automated gate asserts, so the proof can't
# flake on a slow/loaded box. The per-family *reported* time is what shows the real (sub-second)
# interactive cost; this only certifies "interactive-class, not minutes".
RERENDER_CEILING_S = 5.0
# How far the actual rendered envelope may drift from the family's analytic expected_bbox.
BBOX_TOLERANCE_MM = 0.05


class _NoModelProvider:
    """A provider whose only job is to prove it is never used. The deterministic re-render
    path calls no model; if it ever did, these raise instead of silently invoking an LLM."""

    def generate_design_plan(self, *a: Any, **k: Any) -> Any:
        raise AssertionError("deterministic template path must not generate a plan via the model")

    def generate_openscad(self, *a: Any, **k: Any) -> Any:
        raise AssertionError("deterministic template path must not call the model for OpenSCAD")


@dataclass(frozen=True)
class FamilyBench:
    """One family's measured proof. ``rerender_s`` is the live-slider cost (a single
    parameter-change re-render through the real pipeline)."""

    name: str
    rendered: bool
    watertight: bool
    gate_status: str | None
    bbox_error_mm: float  # max abs per-axis error vs the declared expected_bbox
    initial_render_s: float
    rerender_s: float
    deterministic_emit: bool  # emit(values) is byte-identical across calls
    error: str | None = None

    @property
    def ok(self) -> bool:
        return (
            self.error is None
            and self.rendered
            and self.watertight
            and self.deterministic_emit
            and self.bbox_error_mm <= BBOX_TOLERANCE_MM
            and self.rerender_s <= RERENDER_CEILING_S
        )

    @property
    def meets_target(self) -> bool:
        """Whether this re-render hit the <1 s interactive target on this run."""
        return self.error is None and self.rerender_s <= RERENDER_TARGET_S


@dataclass(frozen=True)
class BenchReport:
    families: tuple[FamilyBench, ...]
    environment: dict[str, str]
    binary_present: bool

    @property
    def ok(self) -> bool:
        return bool(self.families) and all(f.ok for f in self.families)

    @property
    def all_meet_target(self) -> bool:
        return bool(self.families) and all(f.meets_target for f in self.families)

    def to_markdown(self, *, date: str | None = None) -> str:
        # ASCII-only: this is printed to the console too, which is cp1252 on Windows (the same
        # trap kimcad.benchmark guards against). GitHub renders plain ASCII tables fine.
        lines = [
            "# Stage 5 - deterministic template-family benchmark",
            "",
            "Every built-in template family, re-rendered through the real "
            "`Pipeline.rerender` path (the same one `POST /api/render` runs): "
            "emit -> OpenSCAD -> validate -> orient -> harden -> export. No prompt, no model "
            "call -- `rerender` invokes no LLM, and the benchmark wires a provider that "
            "*raises* if one is ever called, so \"no model\" is enforced, not assumed.",
            "",
        ]
        if date:
            lines += [f"**Generated:** {date}", ""]
        env = self.environment
        lines += [
            "**Environment**",
            "",
            f"- Platform: `{env.get('platform', '?')}`",
            f"- Processor: `{env.get('processor', '?')}`",
            f"- Python: `{env.get('python', '?')}`",
            "",
            f"**Targets:** re-render under {RERENDER_TARGET_S:g}s (interactive); "
            f"automated gate ceiling {RERENDER_CEILING_S:g}s; "
            f"envelope tolerance {BBOX_TOLERANCE_MM:g} mm.",
            "",
        ]
        if not self.binary_present:
            lines += [
                "> WARNING: OpenSCAD binary not present -- rendering could not run; "
                "timings/envelope checks are unavailable in this report.",
                "",
            ]
        lines += [
            "| Family | Re-render (s) | Under 1s | Initial (s) | bbox err (mm) | Watertight | "
            "No model |",
            "| --- | ---: | :---: | ---: | ---: | :---: | :---: |",
        ]
        for f in self.families:
            if f.error:
                lines.append(f"| `{f.name}` | - | - | - | - | - | ERROR: {f.error} |")
                continue
            lines.append(
                f"| `{f.name}` | {f.rerender_s:.3f} | {'yes' if f.meets_target else 'no'} | "
                f"{f.initial_render_s:.3f} | {f.bbox_error_mm:.4f} | "
                f"{'yes' if f.watertight else 'NO'} | yes |"
            )
        verdict = "PASS" if self.ok else "FAIL"
        target = "all families under 1s" if self.all_meet_target else "see per-family column"
        lines += [
            "",
            f"**Verdict: {verdict}** -- every family renders watertight at its declared "
            f"envelope, deterministically, with no model call, under the "
            f"{RERENDER_CEILING_S:g}s gate ({target}).",
            "",
        ]
        return "\n".join(lines)


def environment() -> dict[str, str]:
    return {
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine() or "unknown",
        "python": platform.python_version(),
    }


def _perturb(family: TemplateFamily, defaults: dict[str, float]) -> dict[str, float]:
    """A small, in-range, gate-safe change to the first parameter — enough to force a real
    geometry change (so the re-render isn't a no-op) without tripping the build-volume gate.

    ENG-507: this assumes ``family.params[0]`` is a geometry-affecting (linear) dimension —
    true for every family in the registry. A future family whose first parameter is cosmetic
    (a toggle that doesn't change the mesh) would make the bench measure a no-op re-render; if
    that happens, pick the first param with a non-empty bbox contribution instead."""
    p = family.params[0]
    target = p.default + p.step if p.default + p.step <= p.max else p.default - p.step
    return clamp_values(family, {**defaults, p.name: target})


def _bench_one(pipe: Pipeline, family: TemplateFamily) -> FamilyBench:
    try:
        defaults = clamp_values(family, {})
        base = DesignPlan(
            object_type=family.object_types[0],
            summary=f"benchmark {family.name}",
            dimensions=dict(defaults),
            bounding_box_mm=list(family.expected_bbox(defaults)),
            printer=pipe.printer.key,
            material=pipe.material.key,
        )
        with TemporaryDirectory() as td:
            out = Path(td)
            t0 = time.perf_counter()
            pipe.rerender(base, family.name, defaults, out, basename="init")
            initial_s = time.perf_counter() - t0

            perturbed = _perturb(family, defaults)
            t1 = time.perf_counter()
            result = pipe.rerender(base, family.name, perturbed, out, basename="re")
            rerender_s = time.perf_counter() - t1

        report = result.report
        rendered = (
            result.status in (PipelineStatus.completed, PipelineStatus.gate_failed)
            and report is not None
        )
        # Determinism + no-model evidence in one check: the SCAD the pipeline actually rendered
        # must equal a fresh PURE emit of the (clamped) perturbed values. If a model had written
        # the geometry, or emit had drifted to something order-dependent, these would differ.
        deterministic = result.scad == emit_scad(family, clamp_values(family, perturbed))
        expected = family.expected_bbox(clamp_values(family, perturbed))
        actual = report.actual_bbox_mm if report else None
        bbox_error = (
            max(abs(a - e) for a, e in zip(actual, expected))
            if actual is not None
            else float("inf")
        )
        return FamilyBench(
            name=family.name,
            rendered=rendered,
            watertight=bool(report and report.watertight),
            gate_status=report.gate_status if report else None,
            bbox_error_mm=bbox_error,
            initial_render_s=initial_s,
            rerender_s=rerender_s,
            deterministic_emit=deterministic,
        )
    except Exception as e:  # one family's failure is a finding, not a crash of the whole run
        return FamilyBench(
            name=family.name,
            rendered=False,
            watertight=False,
            gate_status=None,
            bbox_error_mm=float("inf"),
            initial_render_s=0.0,
            rerender_s=0.0,
            deterministic_emit=False,
            error=f"{type(e).__name__}: {e}",
        )


def benchmark_families(
    cfg: Config | None = None, registry: TemplateRegistry | None = None
) -> BenchReport:
    """Render + re-render every built-in family through the deterministic pipeline path and
    measure it. Requires the OpenSCAD binary; if it's absent, the report flags that and the
    per-family rows carry the render error."""
    cfg = cfg or Config.load()
    registry = registry or default_registry()
    try:
        binary_present = cfg.binary_path("openscad").exists()
    except Exception:
        binary_present = False
    pipe = Pipeline(cfg, cfg.printer(None), cfg.material(None), _NoModelProvider(), registry=registry)
    families = tuple(_bench_one(pipe, fam) for fam in registry.families())
    return BenchReport(families, environment(), binary_present)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark the deterministic template families.")
    parser.add_argument("--write", type=Path, default=None, help="Write the markdown proof here.")
    parser.add_argument("--date", default=None, help="Stamp this date in a written report.")
    args = parser.parse_args(argv)

    report = benchmark_families()
    md = report.to_markdown(date=args.date)
    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(md + "\n", encoding="utf-8")
        print(f"Wrote {args.write}")
    else:
        print(md)
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
