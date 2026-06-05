import { describe, expect, it } from 'vitest'
import { DESIGN_PHASES, phaseLabel, phaseStep } from './designPhase'

describe('designPhase', () => {
  it('orders the four phases planning → generating → rendering → validating', () => {
    expect(DESIGN_PHASES).toEqual(['planning', 'generating', 'rendering', 'validating'])
  })

  it('maps each known phase to a plain-language label', () => {
    expect(phaseLabel('planning')).toMatch(/plan/i)
    expect(phaseLabel('generating')).toBeTruthy()
    expect(phaseLabel('rendering')).toMatch(/3D model/i)
    expect(phaseLabel('validating')).toMatch(/print/i)
  })

  it('returns a null label and step 0 for an unknown or absent phase', () => {
    expect(phaseLabel(null)).toBeNull()
    expect(phaseLabel(undefined)).toBeNull()
    expect(phaseLabel('bogus')).toBeNull()
    expect(phaseStep(null)).toBe(0)
    expect(phaseStep('bogus')).toBe(0)
  })

  it('reports the 1-based step for each phase', () => {
    expect(phaseStep('planning')).toBe(1)
    expect(phaseStep('generating')).toBe(2)
    expect(phaseStep('rendering')).toBe(3)
    expect(phaseStep('validating')).toBe(4)
  })
})
