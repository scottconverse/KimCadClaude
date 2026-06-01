import type { ConnectorStatusResponse } from './api'

// Pure mappers for a printer connection's live readiness. The server never 5xxes and never
// leaks a credential — it returns a typed snapshot (ready / online / state / reason / simulated
// / note). These translate that into the app's green/amber/red scale + an honest label, with
// a loopback/no-hardware connection labelled as simulated rather than narrated as a real print.

export type ConnTone = 'pass' | 'warn' | 'fail' | 'neutral'

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
  if (status.ready) return status.simulated ? 'Ready · simulated' : 'Ready'
  if (status.note) return status.note
  if (status.online === false || status.reason === 'offline') return 'Offline'
  if (status.reason === 'busy' || status.state === 'printing') return 'Busy — printing'
  if (status.state === 'paused') return 'Paused'
  if (status.reason === 'auth') return 'Authentication failed'
  if (status.reason === 'config') return 'Needs setup'
  return 'Not ready'
}
