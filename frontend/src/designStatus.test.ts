import { describe, expect, it } from 'vitest'
import type { DesignResponse } from './api'
import {
  assistantMessage,
  gateLabel,
  gateTone,
  isFailureStatus,
  readinessTone,
} from './designStatus'

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

describe('readinessTone', () => {
  it('maps the readiness tone onto the green/amber/red scale, neutral otherwise', () => {
    expect(readinessTone('pass')).toBe('pass')
    expect(readinessTone('warn')).toBe('warn')
    expect(readinessTone('fail')).toBe('fail')
    expect(readinessTone(undefined)).toBe('neutral')
    expect(readinessTone('weird')).toBe('neutral')
  })
})

describe('isFailureStatus', () => {
  it('marks plan/render/gate failures, not success / clarification / idle', () => {
    expect(isFailureStatus('plan_failed')).toBe(true)
    expect(isFailureStatus('render_failed')).toBe(true)
    expect(isFailureStatus('gate_failed')).toBe(true)
    expect(isFailureStatus('model_unavailable')).toBe(true) // Slice 9: the model-down wall
    expect(isFailureStatus('completed')).toBe(false)
    expect(isFailureStatus('clarification_needed')).toBe(false)
    expect(isFailureStatus(undefined)).toBe(false)
  })
})

describe('gateLabel', () => {
  it('frames the gate badge as the technical check, distinct from the readiness verdict', () => {
    expect(gateLabel('pass')).toBe('Passed')
    expect(gateLabel('warn')).toMatch(/review/i)
    expect(gateLabel('fail')).toBe('Failed')
    // Crucially NOT the readiness headline phrase — the two cards must not duplicate it.
    expect(gateLabel('pass')).not.toMatch(/ready to print/i)
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
    // Slice 9: model_unavailable prefers the backend's actionable message, else a clear default.
    expect(
      assistantMessage({ ...base, status: 'model_unavailable', error: 'Make sure Ollama is running.' }),
    ).toContain('Make sure') // discriminating: a substring unique to the backend error, not the default
    expect(assistantMessage({ ...base, status: 'model_unavailable' })).toMatch(/Ollama|local AI/i)
    expect(assistantMessage({ ...base, status: 'gate_failed' })).toMatch(/printability/i)
    // plan_failed gets a clean, actionable message and does NOT leak the raw parse error.
    const planFailed = assistantMessage({
      ...base,
      status: 'plan_failed',
      error: 'ValidationError: object_type missing',
    })
    expect(planFailed).toMatch(/workable plan/i)
    expect(planFailed).not.toContain('ValidationError')
  })

  it('falls back gracefully when fields are missing', () => {
    expect(
      assistantMessage({ status: 'clarification_needed', has_mesh: false }),
    ).toMatch(/tell me/i)
    expect(assistantMessage({ status: 'render_failed', has_mesh: false })).toMatch(/couldn/i)
  })

  it('uses a sensible fallback for an unrecognised status', () => {
    expect(assistantMessage({ ...base, status: 'something_new' })).toBe(base.plan!.summary)
    expect(assistantMessage({ status: 'something_new', has_mesh: false })).toBe('Done.')
  })
})
