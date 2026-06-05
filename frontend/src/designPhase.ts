// MS-3 — the coarse phases a design run moves through, surfaced as live progress on the
// "Designing…" screen so a multi-minute local run shows WHAT it's doing, not just elapsed seconds.
// These keys match the backend pipeline's progress events (see src/kimcad/pipeline.py DESIGN_PHASES);
// the web layer relays them verbatim through GET /api/design/progress/<job_id>.

export const DESIGN_PHASES = ['planning', 'generating', 'rendering', 'validating'] as const
export type DesignPhase = (typeof DESIGN_PHASES)[number]

// Plain-language, present-progressive labels (a person watching, not a log line).
const PHASE_LABELS: Record<DesignPhase, string> = {
  planning: 'Planning the shape',
  generating: 'Writing the model',
  rendering: 'Building the 3D model',
  validating: 'Checking it for printing',
}

function isPhase(phase: string | null | undefined): phase is DesignPhase {
  return !!phase && (DESIGN_PHASES as readonly string[]).includes(phase)
}

/** The label for a phase, or null for an unknown/absent phase (the UI falls back to a generic line). */
export function phaseLabel(phase: string | null | undefined): string | null {
  return isPhase(phase) ? PHASE_LABELS[phase] : null
}

/** 1-based step number for a phase (1..4), or 0 when the phase is unknown/not yet reported. */
export function phaseStep(phase: string | null | undefined): number {
  return isPhase(phase) ? DESIGN_PHASES.indexOf(phase) + 1 : 0
}
