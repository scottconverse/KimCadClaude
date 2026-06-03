"""Stage 7 — Smart Mesh readiness (spec §6.12).

Smart Mesh is KimCad's **synthesis + history** layer on top of the per-artifact validation
engine. The engine today is the Printability Gate (`kimcad.printability`); when the deeper
geometric / G-code validator **PrintProof3D** is available (Slice 2), its report folds in too.
Smart Mesh ingests what KimCad already knows about a built part — the gate findings, the mesh
integrity stats, the chosen material — plus an *optional* PrintProof3D report, and produces a
single readiness verdict the UI renders as a report card: a 0-100 **score**, a plain **verdict**,
a **confidence**, the **risks**, concrete **recommendations**, and (Slice 5) a **comparison** to
similar past prints. Per the spec, *PrintProof3D is the engine Smart Mesh is built on, not Smart
Mesh itself.*

:func:`assess_readiness` is pure — inputs in, a :class:`MeshReadiness` out — so it is fully
unit-tested without a model, a slicer, or PrintProof3D. The PrintProof3D report is modeled here
as a typed, optional input (:class:`PrintProofReport`); Slice 2 adds the subprocess wrapper that
produces it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kimcad.printability import GateResult, Level
from kimcad.validation import MeshReport

# --- the optional PrintProof3D report (a typed view of validation_report.schema.json) --------
# PrintProof3D severities are its own 5-level scale; KimCad maps them onto the gate's
# pass/warn/fail tone for the card. Slice 2 builds the wrapper that parses the engine's JSON
# into these; here they're an optional input so readiness works with OR without the engine.

_PP_SEVERITIES = ("blocker", "critical", "major", "minor", "nit")
# Score penalty per PrintProof3D issue severity (subtracted from the gate-anchored base).
_PP_PENALTY = {"blocker": 60, "critical": 45, "major": 18, "minor": 6, "nit": 1}
# Which PrintProof3D severities surface as a card "risk", and at what tone.
_PP_RISK_TONE = {"blocker": "fail", "critical": "fail", "major": "warn", "minor": "warn"}


@dataclass(frozen=True)
class PrintProofIssue:
    """One issue from a PrintProof3D ValidationReport."""

    id: str  # the engine's error class, e.g. "OVERHANG_UNSUPPORTED"
    message: str
    severity: str  # one of _PP_SEVERITIES
    suggested_fixes: tuple[str, ...] = ()
    region: str | None = None  # e.g. "base", "overhang"


@dataclass(frozen=True)
class PrintProofReport:
    """A typed view of PrintProof3D's ValidationReport (status / confidence / issues)."""

    status: str  # "pass" | "warning" | "fail"
    confidence_level: str  # the engine's confidence string (free-form)
    issues: tuple[PrintProofIssue, ...] = ()


# --- the readiness verdict the card renders --------------------------------------------------

@dataclass(frozen=True)
class Risk:
    """A single readiness risk shown on the card: a short title + a plain detail + a tone."""

    title: str
    detail: str
    tone: str  # "fail" | "warn" — drives the card's red/amber treatment


@dataclass
class MeshReadiness:
    score: int  # 0-100 -> the gauge
    verdict: str  # "Ready to print" | "Printable with notes" | "Not print-ready"
    tone: str  # "pass" | "warn" | "fail" -> the card color (matches the gate scale)
    confidence: str  # "High" | "Medium" | "Low"
    risks: list[Risk] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    comparison: str | None = None  # historical line; populated by the learning store (Slice 5)
    attribution: str = ""  # what backed this assessment (engine / gate / history)
    sources: list[str] = field(default_factory=list)


# Gate status -> the score the readiness starts from before PrintProof3D penalties apply.
_GATE_BASE = {"pass": 92, "warn": 70, "fail": 38}

# Card tone severity order + the verdict each tone renders as.
_TONE_RANK = {"pass": 0, "warn": 1, "fail": 2}
_VERDICT = {"pass": "Ready to print", "warn": "Printable with notes", "fail": "Not print-ready"}

# KimCad gate finding code -> a short, human risk title. Unknown codes fall back to the
# message itself (truncated), so a new gate check still surfaces sensibly.
_GATE_RISK_TITLE = {
    "dim.mismatch": "Dimensions off target",
    "volume.exceeds": "Too big for the printer",
    "wall.thin": "Walls below the minimum",
    "mesh.not_watertight": "Mesh not watertight",
    "shell.stray": "Stray loose geometry",
}


def _humanize_pp_id(issue_id: str) -> str:
    """`OVERHANG_UNSUPPORTED` -> `Overhang unsupported`. A readable title from the engine id."""
    words = issue_id.replace("_", " ").strip().lower()
    return words[:1].upper() + words[1:] if words else "Printability issue"


def _gate_risk_title(code: str, message: str) -> str:
    title = _GATE_RISK_TITLE.get(code)
    if title:
        return title
    # Unknown code: use the first clause of the message as a title.
    head = message.split(".")[0].split(";")[0].strip()
    return (head[:48] + "...") if len(head) > 49 else (head or "Printability note")


def assess_readiness(
    gate: GateResult,
    mesh_report: MeshReport,
    *,
    material_name: str | None = None,
    printproof: PrintProofReport | None = None,
) -> MeshReadiness:
    """Synthesize a single readiness verdict from the gate + mesh integrity (+ an optional
    PrintProof3D report). Pure: no I/O, deterministic, idempotent."""
    gate_status = str(gate.status)  # "pass" | "warn" | "fail"
    score = _GATE_BASE.get(gate_status, 70)
    sources = ["printability-gate"]
    risks: list[Risk] = []
    recommendations: list[str] = []

    # KimCad gate findings -> risks. FAIL and WARN surface; PASS findings don't.
    for f in gate.findings:
        if f.level is Level.FAIL:
            risks.append(Risk(_gate_risk_title(f.code, f.message), f.message, "fail"))
        elif f.level is Level.WARN:
            risks.append(Risk(_gate_risk_title(f.code, f.message), f.message, "warn"))

    # Mesh integrity the gate may not have FAIL'd on but that lowers confidence.
    mesh_unanalysable = bool(mesh_report.errors)

    # PrintProof3D issues -> score penalty + risks (major+) + recommendations (its suggested fixes).
    if printproof is not None:
        sources.append("printproof3d")
        for issue in printproof.issues:
            score -= _PP_PENALTY.get(issue.severity, 5)
            tone = _PP_RISK_TONE.get(issue.severity)
            if tone is not None:  # blocker/critical/major/minor surface; "nit" doesn't
                risks.append(Risk(_humanize_pp_id(issue.id), issue.message, tone))
            recommendations.extend(issue.suggested_fixes)

    score = max(0, min(100, score))

    # Verdict + tone = the WORST of two independent signals, so the card is never more
    # optimistic than either KimCad's own assessment OR the PrintProof3D engine it cites.
    #  - KimCad's tone: a gate FAIL / sub-50 score / fail-risk -> fail; a gate WARN / sub-80
    #    score / any risk -> warn; else pass (so "Ready to print" is never shown over a risk).
    #  - PrintProof3D's tone: its own overall `status` (fail -> fail, warning -> warn), so a
    #    "fail" report forces "Not print-ready" even if its worst issue only nudged the score.
    has_fail_risk = any(r.tone == "fail" for r in risks)
    if gate_status == "fail" or score < 50 or has_fail_risk:
        kc_tone = "fail"
    elif gate_status == "warn" or score < 80 or risks:
        kc_tone = "warn"
    else:
        kc_tone = "pass"

    pp_tone = "pass"
    if printproof is not None:
        pp_tone = {"fail": "fail", "warning": "warn", "pass": "pass"}.get(printproof.status, "warn")

    tone = max((kc_tone, pp_tone), key=_TONE_RANK.__getitem__)
    verdict = _VERDICT[tone]

    # A modest, factual recommendation set for Slice 1 (no invented history): the engine's
    # suggested fixes (above) plus an orientation note when an overhang risk is present and a
    # material note when one is known. The history-derived "matches the strongest runs" line
    # arrives with the learning store (Slice 5).
    if any("overhang" in r.title.lower() or "support" in r.detail.lower() for r in risks):
        recommendations.append("Keep the auto-orientation (plate-down) so supports stay minimal.")
    if material_name and tone != "fail":
        recommendations.append(f"Slice for {material_name} on the selected printer's profile.")

    confidence = _confidence(printproof, mesh_unanalysable)
    attribution = _attribution(printproof, mesh_unanalysable)

    return MeshReadiness(
        score=score,
        verdict=verdict,
        tone=tone,
        confidence=confidence,
        risks=risks,
        recommendations=_dedupe(recommendations),
        comparison=None,
        attribution=attribution,
        sources=sources,
    )


def _confidence(printproof: PrintProofReport | None, mesh_unanalysable: bool) -> str:
    """High = the deeper engine ran and the geometry was analysable; Medium = KimCad gate only;
    Low = the mesh couldn't be fully analysed (so any verdict is provisional)."""
    if mesh_unanalysable:
        return "Low"
    if printproof is not None:
        return "High"
    return "Medium"


def _attribution(printproof: PrintProofReport | None, mesh_unanalysable: bool) -> str:
    if mesh_unanalysable:
        return "KimCad printability gate (mesh only partly analysable)"
    if printproof is not None:
        # The "your local print history" half is added once the learning store lands (Slice 5).
        return "PrintProof3D validation engine"
    return "KimCad printability gate"


def _dedupe(items: list[str]) -> list[str]:
    """Order-preserving de-dup so an engine fix and a KimCad note don't print twice."""
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
