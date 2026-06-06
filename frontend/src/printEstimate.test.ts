import { describe, expect, it } from 'vitest'
import { buildEstimateRows, formatFilamentLength, formatFilamentWeight } from './printEstimate'

describe('formatFilamentLength', () => {
  it('shows whole millimetres below a metre', () => {
    expect(formatFilamentLength(842.6)).toBe('843 mm')
    expect(formatFilamentLength(1)).toBe('1 mm')
  })
  it('rolls up to metres (2 dp) at and past a metre', () => {
    expect(formatFilamentLength(1000)).toBe('1.00 m')
    expect(formatFilamentLength(3120)).toBe('3.12 m')
  })
  it('returns null for missing / non-positive / non-finite input', () => {
    expect(formatFilamentLength(null)).toBeNull()
    expect(formatFilamentLength(undefined)).toBeNull()
    expect(formatFilamentLength(0)).toBeNull()
    expect(formatFilamentLength(Number.NaN)).toBeNull()
  })
})

describe('formatFilamentWeight', () => {
  it('shows grams to one decimal', () => {
    expect(formatFilamentWeight(9.34)).toBe('9.3 g')
    expect(formatFilamentWeight(12)).toBe('12.0 g')
  })
  it('returns null for missing / non-positive input', () => {
    expect(formatFilamentWeight(null)).toBeNull()
    expect(formatFilamentWeight(0)).toBeNull()
  })
})

describe('buildEstimateRows', () => {
  it('builds labeled rows in order, only for reported fields', () => {
    const rows = buildEstimateRows({
      time: '1h 12m',
      layers: 84,
      filament_mm: 3120,
      filament_cm3: 7.5,
      filament_g: 9.3,
    })
    expect(rows.map((r) => r.key)).toEqual(['time', 'layers', 'length', 'weight'])
    expect(rows.find((r) => r.key === 'time')?.value).toBe('~1h 12m')
    expect(rows.find((r) => r.key === 'length')?.value).toBe('3.12 m')
    expect(rows.find((r) => r.key === 'weight')?.value).toBe('9.3 g')
  })

  it('omits fields the slicer did not report (no fabricated zeros)', () => {
    const rows = buildEstimateRows({
      time: null,
      layers: 50,
      filament_mm: null,
      filament_cm3: null,
      filament_g: null,
    })
    expect(rows.map((r) => r.key)).toEqual(['layers'])
  })

  it('returns no rows for a null/empty estimate', () => {
    expect(buildEstimateRows(null)).toEqual([])
    expect(
      buildEstimateRows({
        time: null,
        layers: null,
        filament_mm: null,
        filament_cm3: null,
        filament_g: null,
      }),
    ).toEqual([])
  })
})
