import type { ConnectorStatusResponse } from './api'

// Pure mappers for a printer connection's live readiness. The server never 5xxes and never
// leaks a credential — it returns a typed snapshot (ready / online / state / reason / simulated
// / note). These translate that into the app's green/amber/red scale + an honest label, with
// a loopback/no-hardware connection labelled as simulated rather than narrated as a real print.

export type ConnTone = 'pass' | 'warn' | 'fail' | 'neutral'

// UX-001 (b4 audit): connector NAMES come from config KEYS ("bambu_p2s", "mock") — never show
// the raw key to the user. This is the one place key→label prettification lives so the Export
// ConnectorStatus, the SendPanel picker, and the ConnectionsCard all agree. The VALUE sent to the
// server stays the exact key; this is purely the display string.
//   - `mock` is the built-in no-hardware loopback → "Built-in preview" (not a developer placeholder).
//   - any other key → Title Case from snake_case ("bambu_p2s" → "Bambu P2S"), with all-digit or
//     short (≤2 char) tokens upper-cased so model numbers/abbreviations read right.
export function displayName(key: string): string {
  if (key === 'mock') return 'Built-in preview'
  return key
    .split('_')
    .map((w) => (/\d/.test(w) || w.length <= 2 ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1)))
    .join(' ')
}

export function connectorTone(status: ConnectorStatusResponse | null): ConnTone {
  if (!status) return 'neutral'
  if (status.ready) return 'pass'
  // online-but-busy is amber; offline / error / auth / config / unknown is red.
  if (status.reason === 'busy' || status.state === 'printing' || status.state === 'paused') {
    return 'warn'
  }
  return 'fail'
}

export function connectorLabel(status: ConnectorStatusResponse | null): string {
  if (!status) return 'Checking…'
  // UX-001 (b4 audit): a simulated (loopback / no-hardware) connection must describe the
  // CONNECTION, not the slice — "Ready · simulated" sat one line above the Slice button and read
  // as "the slice is simulated". Reserve "Ready" for real connected hardware; say plainly that no
  // printer is connected here.
  if (status.ready) return status.simulated ? 'No printer connected' : 'Ready'
  if (status.note) return status.note
  if (status.online === false || status.reason === 'offline') return 'Offline'
  if (status.reason === 'busy' || status.state === 'printing') return 'Busy — printing'
  if (status.state === 'paused') return 'Paused'
  if (status.reason === 'auth') return 'Authentication failed'
  if (status.reason === 'config') return 'Needs setup'
  return 'Not ready'
}
