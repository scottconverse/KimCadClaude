import { useCallback, useEffect, useSyncExternalStore } from 'react'

// KC-18 / UI-v2 slice 1 (#23) — the light/dark theme preference.
//
// Three states: 'light', 'dark', or 'system' (the default — follow the OS). The RESOLVED
// theme is applied as the `kc-theme-dark` class on <html>, which flips the entire token set
// in styles.css (no per-component theming). Same external-store shape as useUnits so every
// call site (the Settings card, the top bar toggle) shares one source of truth, and a
// system-preference change re-resolves live without a reload.

export type ThemePref = 'light' | 'dark' | 'system'

const THEME_PREF = 'kc-theme'
const DARK_CLASS = 'kc-theme-dark'

function getSnapshot(): ThemePref {
  try {
    const raw = localStorage.getItem(THEME_PREF)
    return raw === 'light' || raw === 'dark' ? raw : 'system'
  } catch {
    return 'system'
  }
}

function getServerSnapshot(): ThemePref {
  return 'system'
}

function systemPrefersDark(): boolean {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

/** The theme actually in effect for a given preference. */
export function resolveTheme(pref: ThemePref): 'light' | 'dark' {
  if (pref === 'system') return systemPrefersDark() ? 'dark' : 'light'
  return pref
}

/** Flip the <html> class to match the resolved theme. Idempotent. */
export function applyTheme(pref: ThemePref): void {
  document.documentElement.classList.toggle(DARK_CLASS, resolveTheme(pref) === 'dark')
}

const listeners = new Set<() => void>()

function notify(): void {
  applyTheme(getSnapshot())
  for (const l of listeners) l()
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange)
  function onStorage(e: StorageEvent) {
    if (e.key === THEME_PREF) notify()
  }
  window.addEventListener('storage', onStorage)
  return () => {
    listeners.delete(onChange)
    window.removeEventListener('storage', onStorage)
  }
}

/** Set the app-wide theme preference, persist it, apply it, and notify every subscriber. */
export function setThemePref(pref: ThemePref): void {
  try {
    localStorage.setItem(THEME_PREF, pref)
  } catch {
    /* storage unavailable — the in-memory apply below still themes this session */
  }
  notify()
}

/** Apply the persisted theme at startup (called once from main.tsx, before first paint
 *  settles, so a dark-preference user never sees a light flash on reload). */
export function initTheme(): void {
  applyTheme(getSnapshot())
}

export function useTheme() {
  const pref = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)

  // While following the system, a live OS-level appearance change re-resolves the class.
  useEffect(() => {
    if (pref !== 'system') return
    let mq: MediaQueryList
    try {
      mq = window.matchMedia('(prefers-color-scheme: dark)')
    } catch {
      return
    }
    const onChange = () => applyTheme('system')
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [pref])

  const setTheme = useCallback((p: ThemePref) => setThemePref(p), [])
  return { pref, resolved: resolveTheme(pref), setTheme }
}
