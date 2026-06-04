import { useCallback, useSyncExternalStore } from 'react'

// Stage 8.5 Slice 4 — units preference (mm / inch).
//
// The backend always works in mm. This hook stores the user's *display* preference and exposes
// helpers to convert between mm and the display unit. The preference is a single app-wide value
// (one user, one machine) persisted in localStorage.
//
// It is backed by a module-level external store (via useSyncExternalStore) rather than per-component
// useState so that EVERY call site shares one source of truth: toggling the unit in the Parameters
// card must instantly re-render the Printability dims table too. With independent useState instances
// they would drift until a remount — a real bug this design avoids.

export type Unit = 'mm' | 'in'

const UNITS_PREF = 'kc-units'
const MM_PER_INCH = 25.4

/** Read the current preference straight from localStorage. Returns a stable primitive, so it is
 *  safe as a useSyncExternalStore snapshot (Object.is equal when unchanged → no render loop). */
function getSnapshot(): Unit {
  try {
    return localStorage.getItem(UNITS_PREF) === 'in' ? 'in' : 'mm'
  } catch {
    return 'mm'
  }
}

// Server snapshot (SSR / no window): default to mm.
function getServerSnapshot(): Unit {
  return 'mm'
}

const listeners = new Set<() => void>()

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange)
  // Cross-tab changes: another tab wrote the preference → re-read and notify.
  function onStorage(e: StorageEvent) {
    if (e.key === UNITS_PREF) onChange()
  }
  window.addEventListener('storage', onStorage)
  return () => {
    listeners.delete(onChange)
    window.removeEventListener('storage', onStorage)
  }
}

/** Set the app-wide unit preference, persist it, and notify every subscribed component. */
export function setUnitPref(u: Unit): void {
  try {
    localStorage.setItem(UNITS_PREF, u)
  } catch {
    /* storage unavailable — the in-memory notify below still updates this session */
  }
  for (const l of listeners) l()
}

export function useUnits() {
  const unit = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)

  const setUnit = useCallback((u: Unit) => setUnitPref(u), [])

  /** Convert a mm value to the display unit. */
  const toDisplay = useCallback((mm: number): number => {
    return unit === 'in' ? mm / MM_PER_INCH : mm
  }, [unit])

  /** Convert a display-unit value back to mm. */
  const fromDisplay = useCallback((val: number): number => {
    return unit === 'in' ? val * MM_PER_INCH : val
  }, [unit])

  /** Format a mm value as a display string (rounds sensibly per unit). Inch uses 3 dp (UX-004 —
   *  2 dp was too coarse for thin, print-critical features like nozzle-multiple walls); trailing
   *  zeros are trimmed so 80mm reads "3.15", not "3.150". */
  const formatMm = useCallback((mm: number): string => {
    if (unit === 'in') {
      const inches = mm / MM_PER_INCH
      return parseFloat(inches.toFixed(3)).toString()
    }
    return Number.isInteger(mm) ? String(mm) : mm.toFixed(1)
  }, [unit])

  return { unit, setUnit, toDisplay, fromDisplay, formatMm }
}
