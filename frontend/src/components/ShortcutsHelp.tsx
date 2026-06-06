import { useEffect, useRef } from 'react'

// Slice 11: a small accessible modal listing the app's keyboard shortcuts. Opened with "?".
// Mirrors the FirstRunWizard a11y pattern: role=dialog + aria-modal, focus on mount, Escape to
// close, and a Tab focus-trap so keyboard focus can't escape the dialog while it's open.
export const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: '?', action: 'Show this help' },
  { keys: 'N', action: 'Start a new design' },
  { keys: 'D', action: 'Open My Designs' },
  { keys: ',', action: 'Open Settings' },
  { keys: 'Esc', action: 'Cancel a running design, or close this' },
]

export default function ShortcutsHelp({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    // Remember what had focus so we can hand it back when the dialog closes (a11y: focus must not
    // be dropped to <body> after a modal).
    const previouslyFocused = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      const root = dialogRef.current
      if (!root) return
      const f = Array.from(
        root.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      )
      if (f.length === 0) return
      const first = f[0]
      const last = f[f.length - 1]
      const active = document.activeElement
      if (e.shiftKey && (active === first || active === root)) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previouslyFocused?.focus?.()
    }
  }, [onClose])

  return (
    // The backdrop closes on click; the dialog stops propagation so an inside click doesn't close.
    <div className="kc-modal-backdrop" onClick={onClose}>
      <div
        ref={dialogRef}
        className="kc-shortcuts-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="kc-shortcuts-title"
        // Programmatically focusable (not a tab stop) so the focus-trap's active===root branch is
        // real and a zero-focusable dialog could still hold focus.
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="kc-shortcuts-title" className="kc-shortcuts-title">
          Keyboard shortcuts
        </h2>
        <dl className="kc-shortcuts-list">
          {SHORTCUTS.map((s) => (
            <div className="kc-shortcut-row" key={s.keys}>
              <dt>
                <kbd className="kc-kbd">{s.keys}</kbd>
              </dt>
              <dd>{s.action}</dd>
            </div>
          ))}
        </dl>
        <p className="kc-muted-note">These work when you&rsquo;re not typing in a field.</p>
        <button ref={closeRef} type="button" className="kc-btn kc-btn-accent" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  )
}
