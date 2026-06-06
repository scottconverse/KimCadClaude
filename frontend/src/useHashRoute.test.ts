// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { parseHash, useHashRoute } from './useHashRoute'

afterEach(() => {
  window.location.hash = ''
})

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

describe('useHashRoute (hook) — TEST-002', () => {
  it('updates the route when a hashchange fires', () => {
    const { result } = renderHook(() => useHashRoute())
    expect(result.current.route).toEqual({ name: 'landing' })
    act(() => {
      window.location.hash = '/designs'
      window.dispatchEvent(new Event('hashchange')) // jsdom doesn't always fire it implicitly
    })
    expect(result.current.route).toEqual({ name: 'designs' })
  })

  it('navigate(replace) updates the route directly (replaceState fires no hashchange)', () => {
    const { result } = renderHook(() => useHashRoute())
    act(() => {
      result.current.navigate('design/xyz', { replace: true })
    })
    expect(result.current.route).toEqual({ name: 'design', id: 'xyz' })
    expect(window.location.hash).toBe('#/design/xyz')
  })

  it('navigate() without replace sets the hash and routes there', () => {
    const { result } = renderHook(() => useHashRoute())
    act(() => {
      result.current.navigate('settings')
      window.dispatchEvent(new Event('hashchange'))
    })
    expect(result.current.route).toEqual({ name: 'settings' })
  })
})
