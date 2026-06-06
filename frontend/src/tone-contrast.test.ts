// UX-006: an automated WCAG-AA contrast guard over the status TONE tokens. The hex values MIRROR
// styles.css :root — keep them in sync (change a token there, change it here, and this test proves
// the new value still clears AA). This is the guard that would have caught the Stage 4 pass-green
// and Stage 7 warn-amber contrast misses before they shipped.
import { describe, expect, it } from 'vitest'

// --- styles.css :root tone tokens (keep in sync) ---
const SURFACE = '#faf6ee'
const PASS = '#1d7a4e', PASS_TEXT = '#15633d'
const WARN = '#876312', WARN_TEXT = '#6a4e0b'
const FAIL = '#a8431f'

function srgbToLin(c: number): number {
  const s = c / 255
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
function lum(hex: string): number {
  const n = parseInt(hex.slice(1), 16)
  return 0.2126 * srgbToLin((n >> 16) & 255) + 0.7152 * srgbToLin((n >> 8) & 255) + 0.0722 * srgbToLin(n & 255)
}
function contrast(a: string, b: string): number {
  const la = lum(a), lb = lum(b)
  const [hi, lo] = la > lb ? [la, lb] : [lb, la]
  return (hi + 0.05) / (lo + 0.05)
}
/** color-mix(in srgb, tone pct, base) -> hex, matching the CSS the badges use. */
function mix(tone: string, pct: number, base: string): string {
  const t = parseInt(tone.slice(1), 16), bs = parseInt(base.slice(1), 16)
  const ch = (sh: number) => Math.round((((t >> sh) & 255) * pct + ((bs >> sh) & 255) * (1 - pct)))
  return '#' + [16, 8, 0].map((sh) => ch(sh).toString(16).padStart(2, '0')).join('')
}

// [label, text token, background]: verdict text on the surface; the confidence/status badge text on
// a 14%-tone tint of the surface (the worst case for that text). Small text -> AA 4.5:1.
const CASES: Array<[string, string, string]> = [
  ['pass verdict', PASS_TEXT, SURFACE],
  ['pass badge', PASS_TEXT, mix(PASS, 0.14, SURFACE)],
  ['warn verdict', WARN_TEXT, SURFACE],
  ['warn badge', WARN_TEXT, mix(WARN, 0.14, SURFACE)],
  ['fail verdict', FAIL, SURFACE],
  ['fail badge', FAIL, mix(FAIL, 0.14, SURFACE)],
]

describe('status tone tokens clear WCAG AA (UX-006 guard)', () => {
  it.each(CASES)('%s text clears 4.5:1', (_label, text, bg) => {
    expect(contrast(text, bg)).toBeGreaterThanOrEqual(4.5)
  })
})
