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
  activeRoute,
  saveState = 'idle',
  savedId = null,
}: {
  showNewDesign: boolean
  onNewDesign: () => void
  onMyDesigns: () => void
  activeRoute?: string
  saveState?: SaveState
  savedId?: string | null
}) {
  const onDesigns = activeRoute === 'designs'
  // UX-001: surface auto-save. While saving -> "Saving…"; once persisted (just saved, or a saved
  // design at rest) -> a "Saved · My Designs" link to the user's work; on failure -> "Couldn't
  // save — retrying" (the app retries automatically). These branches are mutually exclusive.
  const persisted = saveState === 'saved' || (saveState === 'idle' && savedId != null)

  return (
    <header className="kc-topbar">
      <div className="kc-brand">
        <span className="kc-logo">
          <CubeGlyph />
        </span>
        <span className="kc-wordmark">
          Kim<span className="kc-wordmark-accent">Cad</span>
        </span>
      </div>
      <div className="kc-topbar-actions">
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
          <button
            type="button"
            className="kc-savestate kc-savestate-saved"
            onClick={onMyDesigns}
            title="Your work is saved. Open My Designs."
          >
            <span className="kc-savedot" aria-hidden="true" /> Saved · My Designs
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
        {showNewDesign && (
          <button type="button" className="kc-btn kc-btn-dark" onClick={onNewDesign}>
            New design
          </button>
        )}
      </div>
    </header>
  )
}
