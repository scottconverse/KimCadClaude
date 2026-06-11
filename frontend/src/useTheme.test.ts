// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { applyTheme, initTheme, resolveTheme, setThemePref } from './useTheme'

// KC-18 / UI-v2 slice 1 (#23) — the theme store's contract: resolution (incl. following the
// OS), the <html> class application that flips the whole token set, and persistence.

function mockSystemDark(matches: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({
      matches,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
  document.documentElement.classList.remove('kc-theme-dark')
})

describe('useTheme store', () => {
  it('resolves explicit prefs directly and "system" from the OS preference', () => {
    mockSystemDark(true)
    expect(resolveTheme('light')).toBe('light')
    expect(resolveTheme('dark')).toBe('dark')
    expect(resolveTheme('system')).toBe('dark')
    mockSystemDark(false)
    expect(resolveTheme('system')).toBe('light')
  })

  it('applyTheme flips the kc-theme-dark class on <html>', () => {
    mockSystemDark(false)
    applyTheme('dark')
    expect(document.documentElement.classList.contains('kc-theme-dark')).toBe(true)
    applyTheme('light')
    expect(document.documentElement.classList.contains('kc-theme-dark')).toBe(false)
  })

  it('setThemePref persists AND applies immediately', () => {
    mockSystemDark(false)
    setThemePref('dark')
    expect(localStorage.getItem('kc-theme')).toBe('dark')
    expect(document.documentElement.classList.contains('kc-theme-dark')).toBe(true)
    setThemePref('light')
    expect(localStorage.getItem('kc-theme')).toBe('light')
    expect(document.documentElement.classList.contains('kc-theme-dark')).toBe(false)
  })

  it('initTheme applies the persisted preference at startup (no light flash for dark users)', () => {
    mockSystemDark(false)
    localStorage.setItem('kc-theme', 'dark')
    initTheme()
    expect(document.documentElement.classList.contains('kc-theme-dark')).toBe(true)
  })

  it('a garbage stored value falls back to system', () => {
    mockSystemDark(true)
    localStorage.setItem('kc-theme', 'banana')
    initTheme()
    expect(document.documentElement.classList.contains('kc-theme-dark')).toBe(true) // system=dark
  })
})
