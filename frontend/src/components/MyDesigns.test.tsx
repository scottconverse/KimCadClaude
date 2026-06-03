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
})
