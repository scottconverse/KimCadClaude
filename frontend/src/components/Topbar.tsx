import { useEffect, useState } from 'react'
import { getOptions } from '../api'

// Top chrome: brand on the left; a save indicator + "My Designs" + "New design" on the right.
//
// "My Designs" (Stage 8.5) opens the saved-designs library and shows an active state on that route;
// "New design" resets to the landing and shows only in the workspace. The save indicator (UX-001)
// tells the user their work is being kept. The Settings / first-run wizard and the live
// printer-status chip are later Stage 8.5 slices — absent until built rather than dead controls.
type SaveState = 'idle' | 'saving' | 'saved' | 'error'

function CubeGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2 21 7v10l-9 5-9-5V7Z" />
      <path d="M3 7l9 5 9-5" />
      <path d="M12 12v10" />
    </svg>
  )
}

export default function Topbar({
  showNewDesign,
  onNewDesign,
  onMyDesigns,
  onSettings,
  onShowShortcuts,
  onHome,
  activeRoute,
  saveState = 'idle',
  savedId = null,
}: {
  showNewDesign: boolean
  onNewDesign: () => void
  onMyDesigns: () => void
  onSettings: () => void
  // UX-005: open the keyboard-shortcuts help (also reachable via "?"). A visible entry point so the
  // shortcuts aren't an undiscoverable hidden feature.
  onShowShortcuts: () => void
  onHome: () => void
  activeRoute?: string
  saveState?: SaveState
  savedId?: string | null
}) {
  const onDesigns = activeRoute === 'designs'
  const onSettingsRoute = activeRoute === 'settings'
  // UX-006: an always-on printer-status chip — the persistent "what am I targeting?" cue (name +
  // build volume) the design is checked against. A status READOUT, not a model/printer menu (the
  // printer is chosen in Settings / the Export card). Best-effort; absent if options can't load.
  const [printerChip, setPrinterChip] = useState<{ name: string; volume: string | null } | null>(null)
  useEffect(() => {
    let cancelled = false
    // Async IIFE with a total try/catch so a missing fetch (tests) or any options-load failure is
    // swallowed — the chip is best-effort chrome, absent rather than a dead/erroring control.
    void (async () => {
      try {
        const o = await getOptions()
        if (cancelled) return
        const p = o.printers.find((x) => x.key === o.default_printer) ?? o.printers[0]
        if (!p) return
        const v = p.build_volume
        setPrinterChip({ name: p.name, volume: v ? `${v[0]}×${v[1]}×${v[2]} mm` : null })
      } catch {
        /* best-effort */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])
  // UX-001: surface auto-save. While saving -> "Saving…"; once persisted (just saved, or a saved
  // design at rest) -> a "Saved · My Designs" link to the user's work; on failure -> "Couldn't
  // save — retrying" (the app retries automatically). These branches are mutually exclusive.
  const persisted = saveState === 'saved' || (saveState === 'idle' && savedId != null)

  return (
    <header className="kc-topbar">
      <button type="button" className="kc-brand" onClick={onHome} aria-label="KimCad — home">
        <span className="kc-logo">
          <CubeGlyph />
        </span>
        <span className="kc-wordmark">
          Kim<span className="kc-wordmark-accent">Cad</span>
        </span>
      </button>
      <div className="kc-topbar-actions">
        {printerChip && (
          <span
            className="kc-printer-chip"
            title="Target printer — change it in Settings"
            aria-label={`Target printer: ${printerChip.name}${printerChip.volume ? `, build volume ${printerChip.volume}` : ''}`}
          >
            <span className="kc-printer-dot" aria-hidden="true" />
            <span className="kc-printer-chip-name">{printerChip.name}</span>
            {printerChip.volume && <span className="kc-printer-chip-vol">{printerChip.volume}</span>}
          </span>
        )}
        {saveState === 'saving' && (
          <span className="kc-savestate kc-savestate-saving" role="status" aria-live="polite">
            <span className="kc-savedot" aria-hidden="true" /> Saving…
          </span>
        )}
        {saveState === 'error' && (
          <span className="kc-savestate kc-savestate-error" role="status" aria-live="polite">
            Couldn’t save — retrying
          </span>
        )}
        {persisted && (
          // UX-013: just "Saved" — the adjacent "My Designs" nav button already provides the link,
          // so the old "Saved · My Designs" doubled the label. Still a button (a quiet shortcut to
          // the library) with a descriptive title/aria-label.
          <button
            type="button"
            className="kc-savestate kc-savestate-saved"
            onClick={onMyDesigns}
            title="Your work is saved. Open My Designs."
            aria-label="Saved — open My Designs"
          >
            <span className="kc-savedot" aria-hidden="true" /> Saved
          </button>
        )}
        <button
          type="button"
          className={`kc-btn kc-btn-ghost${onDesigns ? ' kc-btn-active' : ''}`}
          onClick={onMyDesigns}
          aria-current={onDesigns ? 'page' : undefined}
        >
          My Designs
        </button>
        <button
          type="button"
          className={`kc-btn kc-btn-ghost${onSettingsRoute ? ' kc-btn-active' : ''}`}
          onClick={onSettings}
          aria-current={onSettingsRoute ? 'page' : undefined}
        >
          Settings
        </button>
        <button
          type="button"
          className="kc-btn kc-btn-ghost kc-help-btn"
          onClick={onShowShortcuts}
          aria-label="Keyboard shortcuts"
          title="Keyboard shortcuts (?)"
        >
          ?
        </button>
        {showNewDesign && (
          <button type="button" className="kc-btn kc-btn-dark" onClick={onNewDesign}>
            New design
          </button>
        )}
      </div>
    </header>
  )
}
