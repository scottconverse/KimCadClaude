import { describe, expect, it } from 'vitest'
import { parseHash } from './useHashRoute'

describe('parseHash', () => {
  it('maps each hash to the right route', () => {
    expect(parseHash('')).toEqual({ name: 'landing' })
    expect(parseHash('#/')).toEqual({ name: 'landing' })
    expect(parseHash('#/designs')).toEqual({ name: 'designs' })
    expect(parseHash('#/settings')).toEqual({ name: 'settings' })
    expect(parseHash('#/design/abc123')).toEqual({ name: 'design', id: 'abc123' })
  })

  it('decodes a design id and falls back to landing for an empty id or garbage', () => {
    expect(parseHash('#/design/a%2Db')).toEqual({ name: 'design', id: 'a-b' })
    expect(parseHash('#/design/')).toEqual({ name: 'landing' })
    expect(parseHash('#/nonsense')).toEqual({ name: 'landing' })
  })
})
