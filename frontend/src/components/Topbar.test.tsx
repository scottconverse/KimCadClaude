// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Topbar from './Topbar'

afterEach(cleanup)

function renderBar(overrides: Partial<React.ComponentProps<typeof Topbar>> = {}) {
  const props = {
    showNewDesign: false,
    onNewDesign: vi.fn(),
    onMyDesigns: vi.fn(),
    onSettings: vi.fn(),
    onShowShortcuts: vi.fn(),
    onHome: vi.fn(),
    activeRoute: 'landing',
    ...overrides,
  }
  return { ...render(<Topbar {...props} />), props }
}

describe('Topbar', () => {
  it('renders the My Designs and Settings nav', () => {
    renderBar()
    expect(screen.getByRole('button', { name: 'My Designs' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Settings' })).toBeTruthy()
  })

  it('the brand is a home link (FOUND-001): clicking it calls onHome', () => {
    const { props } = renderBar({ activeRoute: 'settings' })
    fireEvent.click(screen.getByRole('button', { name: /KimCad.*home/i }))
    expect(props.onHome).toHaveBeenCalledTimes(1)
  })

  it('Settings navigates and shows an active state on the settings route', () => {
    const { props } = renderBar({ activeRoute: 'settings' })
    const settings = screen.getByRole('button', { name: 'Settings' })
    expect(settings.getAttribute('aria-current')).toBe('page')
    fireEvent.click(settings)
    expect(props.onSettings).toHaveBeenCalledTimes(1)
  })

  it('shows New design only in the workspace', () => {
    const { rerender } = renderBar({ showNewDesign: false })
    expect(screen.queryByRole('button', { name: 'New design' })).toBeNull()
    rerender(
      <Topbar
        showNewDesign
        onNewDesign={vi.fn()}
        onMyDesigns={vi.fn()}
        onSettings={vi.fn()}
        onShowShortcuts={vi.fn()}
        onHome={vi.fn()}
        activeRoute="landing"
      />,
    )
    expect(screen.getByRole('button', { name: 'New design' })).toBeTruthy()
  })

  it('UX-005: a visible "?" Help button opens the keyboard-shortcuts help', () => {
    const { props } = renderBar()
    fireEvent.click(screen.getByRole('button', { name: /keyboard shortcuts/i }))
    expect(props.onShowShortcuts).toHaveBeenCalledTimes(1)
  })

  it('UX-013: the saved indicator reads just "Saved" (no doubled "My Designs")', () => {
    renderBar({ saveState: 'saved' })
    const saved = screen.getByRole('button', { name: /saved.*my designs/i })
    expect(saved.textContent).toMatch(/Saved/)
    expect(saved.textContent).not.toMatch(/Saved · My Designs/)
  })
})
