import { describe, expect, it } from 'vitest'
import type { ConnectorStatusResponse } from './api'
import { connectorLabel, connectorTone, displayName } from './connectorStatus'

const ready: ConnectorStatusResponse = { name: 'mock', ready: true, simulated: true }

// UX-001 (b4 audit): the centralized key→label prettification — never surface a raw config key.
describe('displayName', () => {
  it('maps the built-in mock connector to a plain product name (never the raw key)', () => {
    expect(displayName('mock')).toBe('Built-in preview')
    expect(displayName('mock')).not.toMatch(/mock/i)
  })

  it('title-cases a snake_case key, upper-casing model-number/abbreviation tokens', () => {
    expect(displayName('bambu_p2s')).toBe('Bambu P2S')
    expect(displayName('octoprint')).toBe('Octoprint')
    expect(displayName('moonraker')).toBe('Moonraker')
  })
})

describe('connectorTone', () => {
  it('maps readiness to the green/amber/red scale', () => {
    expect(connectorTone(null)).toBe('neutral')
    expect(connectorTone(ready)).toBe('pass')
    expect(connectorTone({ name: 'x', ready: false, simulated: false, reason: 'busy' })).toBe('warn')
    expect(connectorTone({ name: 'x', ready: false, simulated: false, state: 'printing' })).toBe(
      'warn',
    )
    expect(connectorTone({ name: 'x', ready: false, simulated: false, state: 'paused' })).toBe(
      'warn',
    )
    expect(connectorTone({ name: 'x', ready: false, simulated: false, reason: 'offline' })).toBe(
      'fail',
    )
  })
})

describe('connectorLabel', () => {
  it('labels readiness honestly and marks a simulated connection', () => {
    expect(connectorLabel(null)).toMatch(/checking/i)
    // UX-001 (b4 audit): the simulated/loopback case describes the CONNECTION (no hardware), and
    // must NOT say "Ready" (reserved for real connected hardware) or "simulated" (read as the
    // slice being simulated, since this sits one line above the Slice button).
    expect(connectorLabel(ready)).toBe('No printer connected')
    expect(connectorLabel(ready)).not.toMatch(/ready/i)
    expect(connectorLabel(ready)).not.toMatch(/simulated/i)
    expect(connectorLabel({ name: 'x', ready: true, simulated: false })).toBe('Ready')
    expect(
      connectorLabel({ name: 'x', ready: false, simulated: false, online: false }),
    ).toMatch(/offline/i)
    expect(
      connectorLabel({ name: 'x', ready: false, simulated: false, note: 'a specific reason' }),
    ).toBe('a specific reason')
  })

  it('derives a label from state/reason when there is no note', () => {
    expect(connectorLabel({ name: 'x', ready: false, simulated: false, state: 'printing' })).toMatch(
      /busy/i,
    )
    expect(connectorLabel({ name: 'x', ready: false, simulated: false, state: 'paused' })).toMatch(
      /paused/i,
    )
    expect(connectorLabel({ name: 'x', ready: false, simulated: false, reason: 'auth' })).toMatch(
      /authentication/i,
    )
    expect(connectorLabel({ name: 'x', ready: false, simulated: false, reason: 'config' })).toMatch(
      /setup/i,
    )
  })
})
