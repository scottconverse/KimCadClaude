// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ShortcutsHelp from './ShortcutsHelp'

afterEach(cleanup)

describe('ShortcutsHelp', () => {
  it('is an accessible modal dialog, focused on Close', () => {
    render(<ShortcutsHelp onClose={vi.fn()} />)
    const dialog = screen.getByRole('dialog')
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    const labelId = dialog.getAttribute('aria-labelledby')
    expect(labelId && document.getElementById(labelId)?.textContent).toMatch(/keyboard shortcuts/i)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: /close/i }))
  })

  it('lists the shortcuts with their keys', () => {
    render(<ShortcutsHelp onClose={vi.fn()} />)
    expect(screen.getByText(/start a new design/i)).toBeTruthy()
    expect(screen.getByText(/open my designs/i)).toBeTruthy()
    expect(screen.getByText(/open settings/i)).toBeTruthy()
  })

  it('Escape and the Close button both call onClose', () => {
    const onClose = vi.fn()
    render(<ShortcutsHelp onClose={onClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('clicking the backdrop closes; clicking inside the dialog does not', () => {
    const onClose = vi.fn()
    const { container } = render(<ShortcutsHelp onClose={onClose} />)
    fireEvent.click(screen.getByRole('dialog'))
    expect(onClose).not.toHaveBeenCalled()
    fireEvent.click(container.querySelector('.kc-modal-backdrop') as HTMLElement)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('traps Tab focus within the dialog (single focusable: Close holds both directions)', () => {
    render(<ShortcutsHelp onClose={vi.fn()} />)
    const dialog = screen.getByRole('dialog')
    const close = screen.getByRole('button', { name: /close/i })
    // Tab while on the only focusable wraps back to it.
    close.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(document.activeElement).toBe(close)
    // Shift+Tab from the only focusable also holds.
    close.focus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(close)
    // Shift+Tab while the dialog root itself is the active element (the active===root branch)
    // pulls focus to the last focusable (Close), not out of the dialog.
    dialog.focus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(close)
  })

  it('restores focus to the trigger when it closes (a11y)', () => {
    // A real trigger button outside the dialog gets focus before the modal opens.
    const trigger = document.createElement('button')
    trigger.textContent = 'open'
    document.body.appendChild(trigger)
    trigger.focus()
    expect(document.activeElement).toBe(trigger)

    const { unmount } = render(<ShortcutsHelp onClose={vi.fn()} />)
    // On mount, focus moved into the dialog (the Close button).
    expect(document.activeElement).toBe(screen.getByRole('button', { name: /close/i }))
    unmount()
    // On close, focus returns to the trigger — not dropped to <body>.
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
  })
})
