// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import MyDesigns from './MyDesigns'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const sample: api.SavedDesignSummary[] = [
  {
    id: 'a1',
    name: 'My Box',
    created_at: '2026-06-03T00:00:00Z',
    object_type: 'box',
    gate_status: 'pass',
    readiness_score: 92,
    has_thumb: true,
    thumb_url: '/api/designs/a1/thumb',
  },
]

describe('MyDesigns', () => {
  it('renders saved designs and opens one when clicked', async () => {
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: sample })
    const onOpen = vi.fn()
    render(<MyDesigns onOpen={onOpen} onNew={vi.fn()} />)
    expect(await screen.findByText('My Box')).toBeTruthy()
    fireEvent.click(screen.getByText('My Box'))
    expect(onOpen).toHaveBeenCalledWith('a1')
  })

  it('shows the empty state when there is nothing saved', async () => {
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: [] })
    render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    expect(await screen.findByText(/Nothing saved yet/i)).toBeTruthy()
  })

  it('deletes a design only after a two-step confirm, then reloads', async () => {
    const getSpy = vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: sample })
    const delSpy = vi.spyOn(api, 'deleteDesign').mockResolvedValue({ ok: true })
    render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    await screen.findByText('My Box')
    // First click arms the confirm — it does NOT delete.
    fireEvent.click(screen.getByText('Delete'))
    expect(delSpy).not.toHaveBeenCalled()
    // Second click (the "Delete?" affordance) confirms.
    fireEvent.click(screen.getByText('Delete?'))
    await waitFor(() => expect(delSpy).toHaveBeenCalledWith('a1'))
    expect(getSpy).toHaveBeenCalledTimes(2) // initial load + reload after delete
  })

  it('cancels an armed delete', async () => {
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: sample })
    const delSpy = vi.spyOn(api, 'deleteDesign').mockResolvedValue({ ok: true })
    render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    await screen.findByText('My Box')
    fireEvent.click(screen.getByText('Delete'))
    fireEvent.click(screen.getByText('Cancel'))
    expect(screen.getByText('Delete')).toBeTruthy() // back to the un-armed state
    expect(delSpy).not.toHaveBeenCalled()
  })

  it('renames a design inline on Enter', async () => {
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: sample })
    const renameSpy = vi.spyOn(api, 'renameDesign').mockResolvedValue({ ok: true })
    render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    await screen.findByText('My Box')
    fireEvent.click(screen.getByText('Rename'))
    const input = screen.getByLabelText('Design name') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'Renamed Box' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(renameSpy).toHaveBeenCalledWith('a1', 'Renamed Box'))
  })

  it('surfaces a load error', async () => {
    vi.spyOn(api, 'getDesigns').mockRejectedValue(new Error('boom'))
    render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    expect(await screen.findByRole('alert')).toBeTruthy()
  })

  it('offers an export download link per card', async () => {
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: sample })
    render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    await screen.findByText('My Box')
    const link = screen.getByText(/Export/).closest('a') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/api/designs/a1/export')
    expect(link.hasAttribute('download')).toBe(true)
    // UX-004: the label names the format so it's not mistaken for a printable STL.
    expect(link.textContent).toMatch(/\.kimcad/)
  })

  it('filters the library by search', async () => {
    const two: api.SavedDesignSummary[] = [
      sample[0],
      { ...sample[0], id: 'b2', name: 'A Bracket', created_at: '2026-06-01T00:00:00Z' },
    ]
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: two })
    render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    await screen.findByText('My Box')
    expect(screen.getByText('A Bracket')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Search your designs'), { target: { value: 'bracket' } })
    expect(screen.queryByText('My Box')).toBeNull()
    expect(screen.getByText('A Bracket')).toBeTruthy()
  })

  it('reorders the grid by the sort control (TEST-005)', async () => {
    const two: api.SavedDesignSummary[] = [
      sample[0], // My Box — created 2026-06-03 (newest)
      { ...sample[0], id: 'b2', name: 'A Bracket', created_at: '2026-06-01T00:00:00Z' },
    ]
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: two })
    render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    await screen.findByText('My Box')
    const names = () =>
      Array.from(document.querySelectorAll('.kc-design-name')).map((n) => n.textContent)
    expect(names()).toEqual(['My Box', 'A Bracket']) // default: newest first
    fireEvent.change(screen.getByLabelText('Sort by'), { target: { value: 'oldest' } })
    expect(names()).toEqual(['A Bracket', 'My Box'])
    fireEvent.change(screen.getByLabelText('Sort by'), { target: { value: 'name' } })
    expect(names()).toEqual(['A Bracket', 'My Box']) // A before M
  })

  it('surfaces a per-card error when an action fails (UX-007)', async () => {
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: sample })
    vi.spyOn(api, 'duplicateDesign').mockRejectedValue(new Error('boom'))
    render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    await screen.findByText('My Box')
    fireEvent.click(screen.getByText('Duplicate'))
    expect(await screen.findByText(/Couldn.t duplicate/i)).toBeTruthy()
  })

  it('shows a no-matches message when the search excludes everything', async () => {
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: sample })
    render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    await screen.findByText('My Box')
    fireEvent.change(screen.getByLabelText('Search your designs'), {
      target: { value: 'zzz-no-such-design' },
    })
    expect(screen.queryByText('My Box')).toBeNull()
    expect(screen.getByText(/No designs match/i)).toBeTruthy()
  })

  it('imports a file and opens the new design', async () => {
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: sample })
    const impSpy = vi.spyOn(api, 'importDesign').mockResolvedValue({ id: 'imp9' })
    const onOpen = vi.fn()
    const { container } = render(<MyDesigns onOpen={onOpen} onNew={vi.fn()} />)
    await screen.findByText('My Box')
    const file = new File([new Uint8Array([0x50, 0x4b])], 'd.kimcad', { type: 'application/zip' })
    const input = container.querySelector('input[type=file]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    // importDesign now also receives an AbortSignal (so the import can be cancelled).
    await waitFor(() => expect(impSpy).toHaveBeenCalledWith(file, expect.any(AbortSignal)))
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith('imp9'))
  })

  it('lets the user cancel an in-flight import and return to the button — never stuck (escape)', async () => {
    vi.spyOn(api, 'getDesigns').mockResolvedValue({ designs: sample })
    vi.spyOn(api, 'importDesign').mockImplementation((_file: File, signal?: AbortSignal) =>
      new Promise((_res, rej) => {
        signal?.addEventListener('abort', () => rej(Object.assign(new Error('aborted'), { name: 'AbortError' })))
      }))
    const { container } = render(<MyDesigns onOpen={vi.fn()} onNew={vi.fn()} />)
    await screen.findByText('My Box')
    const file = new File([new Uint8Array([0x50, 0x4b])], 'd.kimcad', { type: 'application/zip' })
    fireEvent.change(container.querySelector('input[type=file]') as HTMLInputElement, { target: { files: [file] } })
    // Importing… + a Cancel.
    expect(await screen.findByRole('button', { name: /^Cancel$/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Importing/i })).toBeTruthy()
    // Cancel returns to the Import button, no error surfaced.
    fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /^Import$/i })).toBeTruthy())
  })
})
