import { useEffect, useRef } from 'react'

// UX-101 (stage-BCD gate): the app's own confirm — replacing the native window.confirm,
// whose origin-prefixed OS chrome ("127.0.0.1 says…") clashed with the Workshop design
// system, blocked the busy timer, and may be suppressed entirely under the Stage-11
// WebView2 shell. Same a11y discipline as ShortcutsHelp/FirstRunWizard: focus-trapped
// modal, Escape cancels, focus starts on the safe (cancel) action.
export default function ConfirmDialog({
  message,
  confirmLabel,
  cancelLabel = 'Keep working',
  onConfirm,
  onCancel,
}: {
  message: string
  confirmLabel: string
  cancelLabel?: string
  onConfirm: () => void
  onCancel: () => void
}) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)
  // UX-1003 (stage-10 gate): remember what was focused when the dialog opened and put
  // focus BACK there on close — without this, every confirm/cancel dumped keyboard and
  // screen-reader users to the top of the document (verified live in the gate audit).
  const openerRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    openerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    cancelRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onCancel()
        return
      }
      if (e.key !== 'Tab') return
      const root = dialogRef.current
      if (!root) return
      const focusable = Array.from(
        root.querySelectorAll<HTMLElement>('button:not([disabled])'),
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement
      if (e.shiftKey && (active === first || active === root)) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey, true)
    return () => {
      document.removeEventListener('keydown', onKey, true)
      // Restore focus on unmount (the dialog closes by unmounting on BOTH actions).
      // isConnected guards the opener having been removed (e.g. a button that vanished
      // with the action it triggered) — then focus is left for the caller's own flow.
      if (openerRef.current?.isConnected) openerRef.current.focus()
    }
  }, [onCancel])

  return (
    <div
      className="kc-confirm-overlay"
      role="alertdialog"
      aria-modal="true"
      aria-label={message}
      ref={dialogRef}
      tabIndex={-1}
    >
      <div className="kc-confirm">
        <p className="kc-confirm-msg">{message}</p>
        <div className="kc-confirm-actions">
          <button ref={cancelRef} type="button" className="kc-btn" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className="kc-btn kc-btn-accent" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
