import type { DesignResponse } from './api'

// Pure mappers from a design result to UI copy/tone. Kept framework-free so they're unit-
// testable and so the four PipelineStatus values + the gate vocabulary live in one place.

export type GateTone = 'pass' | 'warn' | 'fail' | 'neutral'

/** Map the printability gate_status onto the app's green/amber/red scale. */
export function gateTone(gateStatus: string | undefined): GateTone {
  switch (gateStatus) {
    case 'pass':
      return 'pass'
    case 'warn':
      return 'warn'
    case 'fail':
      return 'fail'
    default:
      return 'neutral'
  }
}

/** Map the Smart Mesh readiness tone ('pass' | 'warn' | 'fail') onto the app's green/amber/red
 * scale. The vocabulary matches the gate's, but a dedicated mapper documents intent and guards an
 * unexpected value to neutral rather than letting it leak into a class name. */
export function readinessTone(tone: string | undefined): GateTone {
  switch (tone) {
    case 'pass':
      return 'pass'
    case 'warn':
      return 'warn'
    case 'fail':
      return 'fail'
    default:
      return 'neutral'
  }
}

/** Label for the printability GATE badge. Framed as the technical gate result ("Passed" /
 * "Needs review" / "Failed"), distinct from the Readiness card's synthesized verdict ("Ready to
 * print"), so the two stacked cards don't lead with the same phrase — the gate is the check that
 * feeds the readiness headline, not a second verdict. */
export function gateLabel(gateStatus: string | undefined): string {
  switch (gateStatus) {
    case 'pass':
      return 'Passed'
    case 'warn':
      return 'Needs review'
    case 'fail':
      return 'Failed'
    default:
      return 'Checked'
  }
}

/** The statuses where the backend produced no usable part — the design attempt failed. The UI
 * uses this to give the chat bubble an error tone and the right-panel cards a "failed" message
 * (distinct from the never-tried-yet idle placeholder). `gate_failed` is included: a part that
 * fails the printability gate is not a usable result on the design surface. */
const FAILURE_STATUSES = new Set(['plan_failed', 'render_failed', 'gate_failed'])

export function isFailureStatus(status: string | undefined): boolean {
  return status !== undefined && FAILURE_STATUSES.has(status)
}

/** The assistant's reply for a design result, branched on every PipelineStatus the backend
 * can return (clarification_needed / plan_failed / render_failed / gate_failed / completed). */
export function assistantMessage(result: DesignResponse): string {
  switch (result.status) {
    case 'clarification_needed':
      return result.clarification || 'Could you tell me a little more about what you need?'
    case 'plan_failed':
      // The model's response couldn't be parsed into a plan. Keep this clean and
      // actionable — don't echo result.error, which carries technical parse details.
      return "I couldn't turn that into a workable plan — the model's response wasn't usable. Try describing the part a little differently, or switch to a model better suited to planning."
    case 'render_failed':
      return result.error
        ? `I couldn't build that one — ${result.error}`
        : "I couldn't build that one. Try describing the part a little differently."
    case 'gate_failed':
      return result.plan
        ? `I made ${result.plan.summary}, but it didn't pass the printability check — see the notes on the right.`
        : "I made it, but it didn't pass the printability check — see the notes on the right."
    case 'completed':
      return result.plan?.summary ? `Here you go — ${result.plan.summary}` : 'Here you go.'
    default:
      return result.plan?.summary || result.clarification || result.error || 'Done.'
  }
}
