import { describe, expect, it } from 'vitest'
import type { ConnectorStatusResponse } from './api'
import { connectorLabel, connectorTone } from './connectorStatus'

const ready: ConnectorStatusResponse = { name: 'mock', ready: true, simulated: true }

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
    expect(connectorLabel(ready)).toMatch(/simulated/i)
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
