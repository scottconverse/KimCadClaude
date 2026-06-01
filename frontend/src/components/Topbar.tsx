// Top chrome: brand on the left; Settings + "New design" on the right.
//
// "New design" is wired (it resets back to the landing) and shows only in the workspace.
// The live printer-status chip is Slice 5; the Settings/first-run wizard is a later stage, so
// the gear is persistent chrome without an action yet.
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

function GearGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
    </svg>
  )
}

export default function Topbar({
  showNewDesign,
  onNewDesign,
}: {
  showNewDesign: boolean
  onNewDesign: () => void
}) {
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
        <button type="button" className="kc-icon-btn" aria-label="Settings">
          <GearGlyph />
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
