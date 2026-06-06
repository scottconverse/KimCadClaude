// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useUnits } from './useUnits'

const MM_PER_INCH = 25.4

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

afterEach(() => {
  localStorage.clear()
})

describe('useUnits', () => {
  it('defaults to mm', () => {
    const { result } = renderHook(() => useUnits())
    expect(result.current.unit).toBe('mm')
  })

  it('restores the persisted preference from localStorage', () => {
    localStorage.setItem('kc-units', 'in')
    const { result } = renderHook(() => useUnits())
    expect(result.current.unit).toBe('in')
  })

  it('setUnit switches the unit and persists to localStorage', () => {
    const { result } = renderHook(() => useUnits())
    act(() => { result.current.setUnit('in') })
    expect(result.current.unit).toBe('in')
    expect(localStorage.getItem('kc-units')).toBe('in')
    act(() => { result.current.setUnit('mm') })
    expect(result.current.unit).toBe('mm')
    expect(localStorage.getItem('kc-units')).toBe('mm')
  })

  it('toDisplay converts mm to inches when unit is in', () => {
    const { result } = renderHook(() => useUnits())
    act(() => { result.current.setUnit('in') })
    expect(result.current.toDisplay(MM_PER_INCH)).toBeCloseTo(1.0)
    expect(result.current.toDisplay(80)).toBeCloseTo(80 / MM_PER_INCH)
  })

  it('toDisplay is identity when unit is mm', () => {
    const { result } = renderHook(() => useUnits())
    expect(result.current.toDisplay(80)).toBe(80)
  })

  it('fromDisplay converts inches back to mm', () => {
    const { result } = renderHook(() => useUnits())
    act(() => { result.current.setUnit('in') })
    expect(result.current.fromDisplay(1)).toBeCloseTo(MM_PER_INCH)
    expect(result.current.fromDisplay(2)).toBeCloseTo(2 * MM_PER_INCH)
  })

  it('round-trips mm → display → mm within 0.01mm', () => {
    const { result } = renderHook(() => useUnits())
    act(() => { result.current.setUnit('in') })
    const original = 80 // mm
    const displayed = result.current.toDisplay(original)
    const backToMm = result.current.fromDisplay(displayed)
    expect(Math.abs(backToMm - original)).toBeLessThan(0.01)
  })

  it('formatMm rounds mm values sensibly', () => {
    const { result } = renderHook(() => useUnits())
    expect(result.current.formatMm(80)).toBe('80')
    expect(result.current.formatMm(80.5)).toBe('80.5')
  })

  it('formatMm in inch mode shows at most 2 decimal places', () => {
    const { result } = renderHook(() => useUnits())
    act(() => { result.current.setUnit('in') })
    const val = result.current.formatMm(80)  // 80mm = 3.1496... in
    expect(val).toBe('3.15')
  })
})
