// Top chrome: brand on the left; "New design" on the right.
//
// "New design" is wired (it resets back to the landing) and shows only in the workspace. The
// Settings / first-run wizard and the live printer-status chip are later stages — rather than
// render an interactive-looking control that does nothing, they're simply absent until built.
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
        {showNewDesign && (
          <button type="button" className="kc-btn kc-btn-dark" onClick={onNewDesign}>
            New design
          </button>
        )}
      </div>
    </header>
  )
}
