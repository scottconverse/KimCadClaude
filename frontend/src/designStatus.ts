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

/** Human label for the gate verdict. */
export function gateLabel(gateStatus: string | undefined): string {
  switch (gateStatus) {
    case 'pass':
      return 'Ready to print'
    case 'warn':
      return 'Printable — with notes'
    case 'fail':
      return 'Not printable yet'
    default:
      return 'Checked'
  }
}

/** The assistant's reply for a design result, branched on every PipelineStatus the backend
 * can return (clarification_needed / render_failed / gate_failed / completed). */
export function assistantMessage(result: DesignResponse): string {
  switch (result.status) {
    case 'clarification_needed':
      return result.clarification || 'Could you tell me a little more about what you need?'
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
