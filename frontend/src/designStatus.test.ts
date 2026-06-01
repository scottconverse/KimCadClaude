import { describe, expect, it } from 'vitest'
import type { DesignResponse } from './api'
import { assistantMessage, gateLabel, gateTone } from './designStatus'

const base: DesignResponse = {
  status: 'completed',
  has_mesh: true,
  mesh_url: '/api/mesh/1',
  plan: { object_type: 'box', summary: 'a wall-mounted spool holder', target_bbox_mm: [80, 60, 40] },
  report: { gate_status: 'pass', headline: 'looks good', dims: [], findings: [] },
}

describe('gateTone', () => {
  it('maps each gate_status onto the green/amber/red scale, neutral otherwise', () => {
    expect(gateTone('pass')).toBe('pass')
    expect(gateTone('warn')).toBe('warn')
    expect(gateTone('fail')).toBe('fail')
    expect(gateTone(undefined)).toBe('neutral')
    expect(gateTone('something-new')).toBe('neutral')
  })
})

describe('gateLabel', () => {
  it('gives a human label per verdict', () => {
    expect(gateLabel('pass')).toMatch(/ready/i)
    expect(gateLabel('warn')).toMatch(/notes/i)
    expect(gateLabel('fail')).toMatch(/not printable/i)
  })
})

describe('assistantMessage', () => {
  it('branches on every PipelineStatus the backend can return', () => {
    expect(assistantMessage({ ...base, status: 'completed' })).toContain('Here you go')
    expect(
      assistantMessage({ ...base, status: 'clarification_needed', clarification: 'How wide?' }),
    ).toBe('How wide?')
    expect(assistantMessage({ ...base, status: 'render_failed', error: 'kaboom' })).toContain(
      'kaboom',
    )
    expect(assistantMessage({ ...base, status: 'gate_failed' })).toMatch(/printability/i)
  })

  it('falls back gracefully when fields are missing', () => {
    expect(
      assistantMessage({ status: 'clarification_needed', has_mesh: false }),
    ).toMatch(/tell me/i)
    expect(assistantMessage({ status: 'render_failed', has_mesh: false })).toMatch(/couldn/i)
  })
})
