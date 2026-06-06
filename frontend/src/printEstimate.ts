// Slice 10 — output clarity. Pure formatters that turn the slicer's structured estimate
// (EstimateDetail) into a labeled breakout the ExportPanel renders as "what you're going to
// get": print time, layer count, filament length, filament weight. Every field is optional —
// a printer profile may not emit a given line — so a missing value yields no row rather than a
// "0" or "—" that would read as a real (wrong) number.
import type { EstimateDetail } from './api'

/** Filament length: meters (2 dp) once it passes a meter, otherwise whole millimetres. */
export function formatFilamentLength(mm: number | null | undefined): string | null {
  if (mm == null || !Number.isFinite(mm) || mm <= 0) return null
  if (mm >= 1000) return `${(mm / 1000).toFixed(2)} m`
  return `${Math.round(mm)} mm`
}

/** Filament weight in grams (1 dp) — the slicer computes this from the real filament density. */
export function formatFilamentWeight(g: number | null | undefined): string | null {
  if (g == null || !Number.isFinite(g) || g <= 0) return null
  return `${g.toFixed(1)} g`
}

export interface EstimateRow {
  key: string
  label: string
  value: string
}

/**
 * Build the labeled breakout rows from a structured estimate. Only fields the slicer actually
 * reported become rows, so the card never shows a fabricated number. Returns [] when there's
 * nothing to show (caller falls back to the plain summary string or a "not available" note).
 */
export function buildEstimateRows(detail: EstimateDetail | null | undefined): EstimateRow[] {
  if (!detail) return []
  const rows: EstimateRow[] = []
  if (detail.time && detail.time.trim() !== '') {
    rows.push({ key: 'time', label: 'Print time', value: `~${detail.time.trim()}` })
  }
  if (detail.layers != null && Number.isFinite(detail.layers) && detail.layers > 0) {
    rows.push({ key: 'layers', label: 'Layers', value: `${detail.layers}` })
  }
  const length = formatFilamentLength(detail.filament_mm)
  if (length) rows.push({ key: 'length', label: 'Filament', value: length })
  const weight = formatFilamentWeight(detail.filament_g)
  if (weight) rows.push({ key: 'weight', label: 'Weight', value: weight })
  return rows
}
