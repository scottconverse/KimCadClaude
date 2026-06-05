import { describe, expect, it } from 'vitest'
import { humanizeObjectType } from './objectType'

describe('humanizeObjectType', () => {
  it('turns slugs into plain words', () => {
    expect(humanizeObjectType('snap_box')).toBe('snap box')
    expect(humanizeObjectType('cable_clip')).toBe('cable clip')
    expect(humanizeObjectType('drawer_divider')).toBe('drawer divider')
    expect(humanizeObjectType('wall-hook')).toBe('wall hook')
  })
  it('collapses repeated/mixed separators and trims', () => {
    expect(humanizeObjectType('  tube__holder ')).toBe('tube holder')
    expect(humanizeObjectType('a_-_b')).toBe('a b')
  })
  it('passes through already-plain words', () => {
    expect(humanizeObjectType('box')).toBe('box')
  })
  it('falls back to "part" for empty/missing', () => {
    expect(humanizeObjectType('')).toBe('part')
    expect(humanizeObjectType(null)).toBe('part')
    expect(humanizeObjectType(undefined)).toBe('part')
    expect(humanizeObjectType('   ')).toBe('part')
  })
})
