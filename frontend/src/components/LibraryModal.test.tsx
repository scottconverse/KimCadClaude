// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

// UI-v2 slice 3 (#23) — the part-library browser: loads the live registry, searches it,
// and a pick submits the family's seed prompt through the normal design flow.

const { getTemplates } = vi.hoisted(() => ({ getTemplates: vi.fn() }))
vi.mock('../api', () => ({ getTemplates }))

import LibraryModal from './LibraryModal'

const FAMILIES = [
  { name: 'tube', summary: 'A ring / cylindrical spacer or standoff.', examples: ['tube', 'ring', 'spacer'], seed: 'a tube', param_count: 3, tier: 'benchmarked' },
  { name: 'wall_hook', summary: 'A wall-mounted hook.', examples: ['hook', 'wall hook'], seed: 'a hook', param_count: 3, tier: 'benchmarked' },
  { name: 'threaded_nut', summary: 'A hex nut (thread relief only).', examples: ['nut', 'hex nut'], seed: 'a nut', param_count: 3, tier: 'baseline' },
]

afterEach(() => {
  cleanup()
  getTemplates.mockReset()
})

describe('LibraryModal', () => {
  it('lists every family with summary + adjustable-dimension count, and a pick submits the seed', async () => {
    getTemplates.mockResolvedValue({ families: FAMILIES })
    const onPick = vi.fn()
    const onClose = vi.fn()
    render(<LibraryModal onPick={onPick} onClose={onClose} />)
    const tubeCard = await screen.findByRole('button', { name: /cylindrical spacer/i })
    expect(screen.getAllByText(/3 adjustable dimensions/)).toHaveLength(3)
    fireEvent.click(tubeCard)
    expect(onPick).toHaveBeenCalledWith('a tube')
    expect(onClose).toHaveBeenCalled()
  })

  it('flags baseline families with a "verify before use" badge; benchmarked ones stay clean (#19)', async () => {
    getTemplates.mockResolvedValue({ families: FAMILIES })
    const { container } = render(<LibraryModal onPick={vi.fn()} onClose={vi.fn()} />)
    await screen.findByRole('button', { name: /cylindrical spacer/i })
    // Exactly one CARD carries the baseline badge (the legend has its own example, excluded).
    const cardBadges = container.querySelectorAll('.kc-library-card .kc-library-tier-baseline')
    expect(cardBadges).toHaveLength(1)
    const nutCard = screen.getByRole('button', { name: /hex nut/i })
    expect(nutCard.textContent).toMatch(/verify before use/i)
    expect(screen.getByRole('button', { name: /cylindrical spacer/i }).textContent).not.toMatch(
      /verify before use/i,
    )
  })

  it('shows an in-UI tier legend with the part count (#19 audit UX-19-1/3)', async () => {
    getTemplates.mockResolvedValue({ families: FAMILIES })
    const { container } = render(<LibraryModal onPick={vi.fn()} onClose={vi.fn()} />)
    await screen.findByRole('button', { name: /cylindrical spacer/i })
    const legend = container.querySelector('.kc-library-legend')
    expect(legend?.textContent).toMatch(/3 parts/)
    expect(legend?.textContent).toMatch(/benchmarked/i)
    expect(legend?.textContent).toMatch(/verify before use/i) // the meaning is visible, not tooltip-only
  })

  it('tier search matches only the whole word, not substrings (#19 audit UX-19-2)', async () => {
    getTemplates.mockResolvedValue({ families: FAMILIES })
    render(<LibraryModal onPick={vi.fn()} onClose={vi.fn()} />)
    await screen.findByRole('button', { name: /cylindrical spacer/i })
    const box = screen.getByLabelText('Search the part library')
    // "baseline" (whole word) filters to the baseline part only.
    fireEvent.change(box, { target: { value: 'baseline' } })
    expect(screen.getByRole('button', { name: /hex nut/i })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /cylindrical spacer/i })).toBeNull()
    // "ba" (a substring of "baseline") must NOT match on tier — it pollutes nothing here.
    fireEvent.change(box, { target: { value: 'ba' } })
    expect(screen.getByText(/designs beyond the library/i)).toBeTruthy()
  })

  it('search filters by name, summary, and aliases', async () => {
    getTemplates.mockResolvedValue({ families: FAMILIES })
    render(<LibraryModal onPick={vi.fn()} onClose={vi.fn()} />)
    await screen.findByRole('button', { name: /cylindrical spacer/i })
    fireEvent.change(screen.getByLabelText('Search the part library'), { target: { value: 'hook' } })
    expect(screen.queryByRole('button', { name: /cylindrical spacer/i })).toBeNull()
    expect(screen.getByRole('button', { name: /wall-mounted hook/i })).toBeTruthy()
    // A no-match search points back at the design box honestly (no dead end).
    fireEvent.change(screen.getByLabelText('Search the part library'), { target: { value: 'spaceship' } })
    expect(screen.getByText(/designs beyond the library/i)).toBeTruthy()
  })

  it('a load failure degrades honestly (the design box still works) and Esc closes', async () => {
    getTemplates.mockRejectedValue(new Error('down'))
    const onClose = vi.fn()
    render(<LibraryModal onPick={vi.fn()} onClose={onClose} />)
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/just describe your part/i))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
