import { describe, expect, it } from 'vitest'

// TST-3 (GauntletGate) — guard the JS-constant ↔ CSS-token equality for the viewport accent.
//
// KCViewport.ts hardcodes `const ACCENT = 0x......` (a Three.js color int) which is documented to
// match the dark theme's `--kc-accent` token in styles.css. The retheme (KimCad → TinkerQuarry)
// drifted these once already (the old 0xd4af37 Zen gold survived in the JS after the CSS moved to
// forge amber). This test reads BOTH source files and asserts the two values are byte-equal, so the
// next palette change can't silently re-open the drift. ACCENT is module-private (intentionally not
// exported just for a test), so we parse the source text rather than importing the symbol.
//
// We read the files with Node's fs at test time. `styles.css?raw` does NOT work here — Vite's CSS
// plugin intercepts `.css` imports even with `?raw`, returning transformed (empty) text. `@types/node`
// is not a dependency of this app (Node is build-time only), so we declare the tiny fs/url surface we
// use locally rather than pulling in the whole type package just for a test.
declare function require(id: string): {
  readFileSync(path: string, enc: 'utf8'): string
  fileURLToPath(url: string | URL): string
}
const { readFileSync } = require('node:fs')
const { fileURLToPath } = require('node:url')

const here = fileURLToPath(new URL('.', import.meta.url))
const viewportSrc: string = readFileSync(`${here}KCViewport.ts`, 'utf8')
const stylesSrc: string = readFileSync(`${here}../styles.css`, 'utf8')

/** The `ACCENT = 0xrrggbb` literal from KCViewport.ts, as a lowercase 6-digit hex. */
function jsAccentHex(): string {
  const m = viewportSrc.match(/const\s+ACCENT\s*=\s*0x([0-9a-fA-F]{6})\b/)
  if (!m) throw new Error('Could not find `const ACCENT = 0x......` in KCViewport.ts')
  return m[1].toLowerCase()
}

/** The `--kc-accent` value inside the `:root.kc-theme-dark { ... }` block in styles.css. */
function cssDarkAccentHex(): string {
  const block = stylesSrc.match(/:root\.kc-theme-dark\s*\{([\s\S]*?)\}/)
  if (!block) throw new Error('Could not find the :root.kc-theme-dark block in styles.css')
  const m = block[1].match(/--kc-accent:\s*#([0-9a-fA-F]{6})\b/)
  if (!m) throw new Error('Could not find --kc-accent inside :root.kc-theme-dark')
  return m[1].toLowerCase()
}

describe('viewport ACCENT matches the dark --kc-accent token (TST-3 drift guard)', () => {
  it('KCViewport.ts ACCENT equals styles.css :root.kc-theme-dark --kc-accent', () => {
    expect(jsAccentHex()).toBe(cssDarkAccentHex())
  })

  it('both values are the expected TinkerQuarry forge amber (e0a667)', () => {
    // A second, explicit pin so a coordinated edit to BOTH files still has to be deliberate.
    expect(jsAccentHex()).toBe('e0a667')
    expect(cssDarkAccentHex()).toBe('e0a667')
  })
})
