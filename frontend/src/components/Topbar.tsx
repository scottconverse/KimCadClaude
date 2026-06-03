// Top chrome: brand on the left; "My Designs" + "New design" on the right.
//
// "My Designs" (Stage 8.5) opens the saved-designs library; "New design" resets to the landing and
// shows only in the workspace. The Settings / first-run wizard and the live printer-status chip are
// later Stage 8.5 slices — absent until built rather than rendered as dead controls.
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
}: {
  showNewDesign: boolean
  onNewDesign: () => void
  onMyDesigns: () => void
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
        <button type="button" className="kc-btn kc-btn-ghost" onClick={onMyDesigns}>
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
