"""Stage 7 — PrintProof3D arm's-length integration (spec §6.11 / §6.12).

PrintProof3D is the owner's MIT Rust validation **engine**. KimCad runs it at arm's length — a
subprocess, never linked — to validate a rendered mesh against the chosen printer + material, and
parses its ``ValidationReport`` JSON into the typed :class:`~kimcad.smart_mesh.PrintProofReport`
that Smart Mesh folds into the readiness verdict. The CLI contract:

    printproof3d validate-model --model <mesh> --printer <printer.json> --material <material.json>
        -o <report.json>

PrintProof3D needs its own printer/material profile JSON (its schema, not KimCad's), so this module
generates a minimal-but-valid profile from KimCad's :class:`~kimcad.config.Printer` /
:class:`~kimcad.config.Material` — the mesh-relevant fields (build volume, nozzle, temps) come from
KimCad; capability flags that don't affect model validation get conservative constants.

**Best-effort + injectable.** :func:`validate_model` returns ``None`` whenever the engine isn't
configured/present, the run produces no report, or the report doesn't parse — so Smart Mesh keeps
working on KimCad's own gate (honestly, at lower confidence). It **never raises**. The run is gated
on the *parsed report file*, not the exit code: PrintProof3D exits non-zero on a fail verdict, which
is a normal result, not a wrapper failure. The subprocess runner is injectable so the wrapper is
unit-tested offline without the binary.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from kimcad.config import Material, Printer
from kimcad.smart_mesh import PrintProofIssue, PrintProofReport

# A runner produces the report at the ``-o`` path in ``argv`` (real: the subprocess; a test fake:
# writes a canned report there). It must not raise to signal a validation *result* — only a
# genuine execution failure. validate_model treats any raise as "no report" and degrades.
Runner = Callable[[list[str], float], None]

_VALID_PP_SEVERITIES = frozenset({"blocker", "critical", "major", "minor", "nit"})


def _subprocess_runner(argv: list[str], timeout_s: float) -> None:
    """Run PrintProof3D as a subprocess (argv list, no shell). The return code is ignored on
    purpose — a non-zero exit is how PrintProof3D reports a fail/warning verdict, not a crash;
    the report file at ``-o`` is the source of truth. A timeout/OS error propagates and is
    caught by the caller (which then degrades to no report). stdout/stderr are captured (not
    inherited, so the engine can't scribble on KimCad's console) and intentionally not surfaced —
    the parsed report, not the engine's chatter, is the contract."""
    subprocess.run(argv, timeout=timeout_s, capture_output=True, check=False)


def validate_model(
    mesh_path: str | Path,
    printer: Printer,
    material: Material,
    *,
    binary: Path | None,
    runner: Runner | None = None,
    timeout_s: float = 120.0,
) -> PrintProofReport | None:
    """Validate ``mesh_path`` with PrintProof3D against ``printer`` + ``material``; return the
    parsed report, or ``None`` if the engine isn't available or the run yields no usable report.
    Never raises.

    The caller must pass a **bed-positioned** STL: PrintProof3D measures the model's extents
    against the build volume from the origin corner ``[0, build]``, so a part centered on the
    origin (X/Y negative) trips a false ``MODEL_OUT_OF_BOUNDS``. The pipeline (Slice 3) translates
    the oriented mesh so its min-corner sits at the bed origin before calling this."""
    if binary is None:
        return None
    run = runner or _subprocess_runner

    with tempfile.TemporaryDirectory(prefix="kimcad-pp3d-") as tmp:
        tmpdir = Path(tmp)
        printer_json = tmpdir / "printer.json"
        material_json = tmpdir / "material.json"
        report_json = tmpdir / "report.json"
        try:
            # allow_nan=False: a non-finite field would emit `Infinity`/`NaN`, which the strict
            # Rust engine rejects; raise here instead and degrade cleanly (caught just below).
            printer_json.write_text(
                json.dumps(printer_profile(printer), allow_nan=False), encoding="utf-8"
            )
            material_json.write_text(
                json.dumps(material_profile(material), allow_nan=False), encoding="utf-8"
            )
        except (OSError, TypeError, ValueError, IndexError, KeyError, AttributeError):
            return None  # any profile-build/serialize failure -> degrade, never raise

        argv = [
            str(binary), "validate-model",
            "--model", str(mesh_path),
            "--printer", str(printer_json),
            "--material", str(material_json),
            "-o", str(report_json),
        ]
        try:
            run(argv, timeout_s)
        except Exception:  # noqa: BLE001 - any execution failure -> degrade, never crash KimCad
            # The run may still have written a partial/whole report before failing; fall through
            # and try to read it. If it didn't, the exists() check below returns None.
            pass

        if not report_json.exists():
            return None
        try:
            data = json.loads(report_json.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return _parse_report(data)


def _parse_report(data: object) -> PrintProofReport | None:
    """Map a PrintProof3D ``ValidationReport`` dict into a :class:`PrintProofReport`. Returns
    None for a non-dict / shapeless body so a malformed engine response degrades cleanly."""
    if not isinstance(data, dict):
        return None
    status = data.get("status")
    if status not in ("pass", "warning", "fail"):
        return None
    issues: list[PrintProofIssue] = []
    issues_raw = data.get("issues")
    issues_raw = issues_raw if isinstance(issues_raw, list) else []  # never iterate a non-list
    for raw in issues_raw:
        if not isinstance(raw, dict):
            continue
        severity = raw.get("severity")
        if severity not in _VALID_PP_SEVERITIES:
            continue  # skip an issue with an unrecognized severity rather than guess
        fixes = raw.get("suggested_fixes")
        fixes = fixes if isinstance(fixes, list) else []
        location = raw.get("location") or {}
        region = location.get("region") if isinstance(location, dict) else None
        issues.append(PrintProofIssue(
            id=str(raw.get("id", "UNKNOWN")),
            message=str(raw.get("message", "")),
            severity=str(severity),
            suggested_fixes=tuple(str(f) for f in fixes if isinstance(f, str)),
            region=str(region) if region else None,
        ))
    return PrintProofReport(
        status=str(status),
        confidence_level=str(data.get("confidence_level", "")),
        issues=tuple(issues),
    )


# --- KimCad Printer/Material -> PrintProof3D profile JSON ------------------------------------
# Minimal-but-valid profiles (the engine's printer_profile / material_profile schema). The
# fields that drive model validation — build volume, nozzle, thermal window, min feature — come
# from KimCad's config; capability flags (cancel/pause/webcam/...) don't affect validate-model,
# so they take conservative constants.

def printer_profile(printer: Printer) -> dict:
    """A PrintProof3D PrinterProfile dict built from KimCad's :class:`Printer`."""
    bv = printer.build_volume or (256.0, 256.0, 256.0)
    nozzle = float(printer.nozzle_diameter) if printer.nozzle_diameter is not None else 0.4
    return {
        "manufacturer": "KimCad",
        "model": printer.name,
        "firmware_flavor": "unknown",
        "protocol_family": "unknown",
        "bed_shape": "rectangular",
        "build_volume": {"type": "rectangular", "x": float(bv[0]), "y": float(bv[1]), "z": float(bv[2])},
        "default_nozzle_diameter": nozzle,
        "nozzle_diameters": [nozzle],
        "max_hotend_temp": 300.0,
        "max_bed_temp": 120.0,
        "min_layer_height": 0.08,
        "max_layer_height": round(nozzle * 0.8, 3),
        "has_enclosure": False,
        "known_quirks": [],
        "unsafe_commands": [],
        "supported_file_types": ["gcode", "3mf", "stl"],
        "supports_cancel": False,
        "supports_chamber_temp": False,
        "supports_direct_upload": False,
        "supports_job_progress": False,
        "supports_mmu": False,
        "supports_pause_resume": False,
        "supports_webcam": False,
    }


def material_profile(material: Material) -> dict:
    """A PrintProof3D MaterialProfile dict built from KimCad's :class:`Material`. The thermal
    window is a band around the configured temps; the risk levels are derived from shrinkage."""
    nozzle_temp = float(material.nozzle_temp)
    bed_temp = float(material.bed_temp)
    # Higher shrinkage -> more warp / harder overhangs (a coarse but honest heuristic).
    warp = "high" if material.shrinkage >= 0.005 else ("medium" if material.shrinkage >= 0.003 else "low")
    return {
        "name": material.name,
        "abbreviations": [material.key.upper()],
        "min_nozzle_temp": nozzle_temp - 15.0,
        "max_nozzle_temp": nozzle_temp + 15.0,
        "min_bed_temp": max(0.0, bed_temp - 10.0),
        "max_bed_temp": bed_temp + 10.0,
        "min_feature_size_mm": round(material.wall_multiplier * 0.2, 3),
        "cooling_fan_speed_pct": 100.0,
        "dryness_sensitive": bool(material.shrinkage >= 0.004),
        "enclosure_recommended": bool(bed_temp >= 90.0),
        "bridge_difficulty": warp,
        "overhang_difficulty": warp,
        "warp_risk": warp,
    }
