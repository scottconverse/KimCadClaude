import { useEffect, useId, useRef, useState } from 'react'
import { GLOSSARY, type GlossaryKey } from '../glossary'

// Slice 9 MS-2 — in-app help / glossary. A small "(i)" button beside a piece of jargon that
// reveals a plain-language definition. It's a click-to-toggle DISCLOSURE (not a hover tooltip) on
// purpose: it never reflows on mere hover/focus, and the definition drops in below the term's row
// anchored to a full-width `.kc-tip-host` ancestor — so it spans the card and never gets clipped
// inside the scrolling side panel (a floating tooltip would).
//
// Accessibility: a real <button> with a descriptive name ("What does X mean?"), aria-expanded for
// the open state, aria-controls tying it to the panel (set only when the panel exists), and the
// panel is a role="note" region. While open, Escape (from anywhere) and a click/tap outside the tip
// both dismiss it.
export default function InfoTip({ term }: { term: GlossaryKey }) {
  const entry = GLOSSARY[term]
  const panelId = useId()
  const wrapRef = useRef<HTMLSpanElement>(null)
  const [open, setOpen] = useState(false)

  // Dismissal listeners are scoped to the open state: they cost nothing when closed and clean up on
  // close/unmount. Binding Escape at the document level (rather than on the button) means it closes
  // the tip regardless of where focus currently is — not only while the trigger stays focused.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    const onPointerDown = (e: PointerEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointerDown)
    }
  }, [open])

  return (
    <span className="kc-infotip" ref={wrapRef}>
      <button
        type="button"
        className="kc-infotip-btn"
        aria-label={`What does “${entry.term}” mean?`}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((o) => !o)}
      >
        <span aria-hidden="true">i</span>
      </button>
      {open && (
        // A phrasing-level <span> on purpose: the tip is anchored inside headings and paragraphs
        // (h2/h3/p), which only allow phrasing content — a <div>/<p> here would be invalid HTML.
        <span role="note" id={panelId} className="kc-infotip-panel">
          {entry.definition}
        </span>
      )}
    </span>
  )
}
