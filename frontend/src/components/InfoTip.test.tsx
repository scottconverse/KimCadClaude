// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { GLOSSARY } from '../glossary'
import InfoTip from './InfoTip'

afterEach(cleanup)

describe('InfoTip', () => {
  it('renders a help button named for the term, with the definition hidden until opened', () => {
    render(<InfoTip term="gate" />)
    const btn = screen.getByRole('button', { name: /what does .*gate.* mean/i })
    expect(btn.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByRole('note')).toBeNull()
  })

  it('click reveals the plain-language definition, sets the aria state, and toggles closed again', () => {
    render(<InfoTip term="readiness" />)
    const btn = screen.getByRole('button', { name: /readiness/i })
    fireEvent.click(btn)
    const panel = screen.getByRole('note')
    expect(panel.textContent).toBe(GLOSSARY.readiness.definition)
    expect(btn.getAttribute('aria-expanded')).toBe('true')
    // The trigger is tied to the panel for assistive tech.
    expect(btn.getAttribute('aria-controls')).toBe(panel.id)
    fireEvent.click(btn)
    expect(screen.queryByRole('note')).toBeNull()
    expect(btn.getAttribute('aria-expanded')).toBe('false')
  })

  it('Escape closes an open definition', () => {
    render(<InfoTip term="printability" />)
    const btn = screen.getByRole('button')
    fireEvent.click(btn)
    expect(screen.getByRole('note')).toBeTruthy()
    fireEvent.keyDown(btn, { key: 'Escape' })
    expect(screen.queryByRole('note')).toBeNull()
  })

  it('closes when focus moves outside the tip (e.g. another surface takes focus)', () => {
    const outside = document.createElement('button')
    document.body.appendChild(outside)
    render(<InfoTip term="gate" />)
    fireEvent.click(screen.getByRole('button', { name: /gate/i }))
    expect(screen.getByRole('note')).toBeTruthy()
    // Focus lands on an element outside the tip wrapper → the disclosure closes.
    outside.focus()
    fireEvent.focusIn(outside)
    expect(screen.queryByRole('note')).toBeNull()
    outside.remove()
  })

  it('surfaces real plain-language copy — not an empty or term-restating definition', () => {
    render(<InfoTip term="confidence" />)
    fireEvent.click(screen.getByRole('button'))
    const text = screen.getByRole('note').textContent ?? ''
    // A genuine explanation: meaningfully longer than the term and not just the word back.
    expect(text.length).toBeGreaterThan(30)
    expect(text.trim().toLowerCase()).not.toBe('confidence')
  })
})
