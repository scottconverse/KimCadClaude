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

  useEffect(() => {
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
    return () => document.removeEventListener('keydown', onKey, true)
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
