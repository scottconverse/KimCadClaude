// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PhotoOnramp from './PhotoOnramp'
import * as api from '../api'

// Mock only uploadPhoto; keep the rest of the api module real.
vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return { ...actual, uploadPhoto: vi.fn() }
})
const mockUpload = api.uploadPhoto as unknown as ReturnType<typeof vi.fn>

beforeEach(() => {
  // jsdom doesn't implement the object-URL APIs the preview thumbnail uses.
  Object.defineProperty(URL, 'createObjectURL', { value: vi.fn(() => 'blob:preview'), writable: true })
  Object.defineProperty(URL, 'revokeObjectURL', { value: vi.fn(), writable: true })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const SEED_LABEL = /Edit the description read from your photo/i

function pickFile(
  container: HTMLElement,
  file = new File([new Uint8Array([1, 2, 3])], 'p.png', { type: 'image/png' }),
) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [file] } })
}

describe('PhotoOnramp', () => {
  it('shows the secondary "Describe with a photo" affordance initially', () => {
    render(<PhotoOnramp onSeed={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Describe with a photo/i })).toBeTruthy()
  })

  it('shows the local-vision reading state, then an editable rough seed + scale disclaimer', async () => {
    let resolve!: (v: { seed: string }) => void
    mockUpload.mockImplementation(() => new Promise((r) => { resolve = r }))
    const { container } = render(<PhotoOnramp onSeed={vi.fn()} />)
    pickFile(container)
    // Honest reading state + the privacy promise.
    expect(await screen.findByText(/Reading your photo/i)).toBeTruthy()
    expect(screen.getByText(/never leaves your machine/i)).toBeTruthy()
    resolve({ seed: 'a rough box, roughly 80mm wide' })
    const box = (await screen.findByLabelText(SEED_LABEL)) as HTMLTextAreaElement
    expect(box.value).toBe('a rough box, roughly 80mm wide')
    expect(screen.getByText(/a photo can.t tell us scale/i)).toBeTruthy()
    // MS2-002: focus moves to the editable seed so AT announces it and editing is immediate.
    expect(document.activeElement).toBe(box)
  })

  it('never auto-submits — onSeed is NOT called from merely reading a photo', async () => {
    mockUpload.mockResolvedValue({ seed: 'a rough box' })
    const onSeed = vi.fn()
    const { container } = render(<PhotoOnramp onSeed={onSeed} />)
    pickFile(container)
    await screen.findByLabelText(SEED_LABEL)
    expect(onSeed).not.toHaveBeenCalled() // the user must explicitly confirm
  })

  it('passes the EDITED seed to onSeed when used as a starting point', async () => {
    mockUpload.mockResolvedValue({ seed: 'a rough box' })
    const onSeed = vi.fn()
    const { container } = render(<PhotoOnramp onSeed={onSeed} />)
    pickFile(container)
    const box = await screen.findByLabelText(SEED_LABEL)
    fireEvent.change(box, { target: { value: 'a rough box, about 100mm wide' } })
    fireEvent.click(screen.getByRole('button', { name: /Use this as a starting point/i }))
    expect(onSeed).toHaveBeenCalledWith('a rough box, about 100mm wide')
    // After using the seed, it returns to the idle affordance.
    expect(screen.getByRole('button', { name: /Describe with a photo/i })).toBeTruthy()
  })

  it('treats a blank seed as a friendly failure, not a silent success', async () => {
    mockUpload.mockResolvedValue({ seed: '   ' })
    const onSeed = vi.fn()
    const { container } = render(<PhotoOnramp onSeed={onSeed} />)
    pickFile(container)
    expect(await screen.findByText(/couldn.t read that photo/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Use a different photo/i })).toBeTruthy()
    expect(onSeed).not.toHaveBeenCalled()
  })

  it('surfaces the upload error message (e.g. a too-large photo) with a fallback', async () => {
    mockUpload.mockRejectedValue(new Error('That photo is too large to read (max 12 MB).'))
    const { container } = render(<PhotoOnramp onSeed={vi.fn()} />)
    pickFile(container)
    expect(await screen.findByText(/too large to read/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Use a different photo/i })).toBeTruthy()
  })

  it('Cancel from the confirm card returns to the affordance without submitting', async () => {
    mockUpload.mockResolvedValue({ seed: 'a rough box' })
    const onSeed = vi.fn()
    const { container } = render(<PhotoOnramp onSeed={onSeed} />)
    pickFile(container)
    await screen.findByLabelText(SEED_LABEL)
    fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }))
    expect(screen.getByRole('button', { name: /Describe with a photo/i })).toBeTruthy()
    expect(onSeed).not.toHaveBeenCalled()
    // MS2-001: the preview blob URL is revoked on reset (no object-URL leak).
    expect(URL.revokeObjectURL).toHaveBeenCalled()
  })

  it('shows the "starts a new part" cue only in the workspace variant', async () => {
    mockUpload.mockResolvedValue({ seed: 'a rough box' })
    const { container, rerender } = render(<PhotoOnramp onSeed={vi.fn()} variant="landing" />)
    pickFile(container)
    await screen.findByLabelText(SEED_LABEL)
    expect(screen.queryByText(/starts a new part from the photo/i)).toBeNull() // landing: no restart cue
    rerender(<PhotoOnramp onSeed={vi.fn()} variant="workspace" />)
    // re-pick in the workspace variant
    pickFile(container)
    await screen.findByLabelText(SEED_LABEL)
    expect(screen.getByText(/starts a new part from the photo/i)).toBeTruthy()
  })

  it('disables the affordance while a design is in flight', () => {
    render(<PhotoOnramp onSeed={vi.fn()} disabled />)
    const btn = screen.getByRole('button', { name: /Describe with a photo/i }) as HTMLButtonElement
    expect(btn.disabled).toBe(true)
  })

  it('accepts a dropped photo (drag-and-drop) and runs the read flow (TEST-703)', async () => {
    mockUpload.mockResolvedValue({ seed: 'a dropped box' })
    render(<PhotoOnramp onSeed={vi.fn()} />)
    const affordance = screen.getByRole('button', { name: /Describe with a photo/i })
    const file = new File([new Uint8Array([1, 2, 3])], 'd.png', { type: 'image/png' })
    // fireEvent returns false when the handler called preventDefault — onDrop must, so the browser
    // doesn't navigate to the dropped image.
    const notCancelled = fireEvent.drop(affordance, { dataTransfer: { files: [file] } })
    expect(notCancelled).toBe(false)
    const box = (await screen.findByLabelText(SEED_LABEL)) as HTMLTextAreaElement
    expect(box.value).toBe('a dropped box') // the drop routed into the same read flow
  })

  it('re-picking via "Use a different photo" swaps the preview and revokes the prior blob URL (TEST-704)', async () => {
    mockUpload.mockResolvedValue({ seed: 'a rough box' })
    const { container } = render(<PhotoOnramp onSeed={vi.fn()} />)
    pickFile(container)
    await screen.findByLabelText(SEED_LABEL)
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    // From the confirm card, choose a different photo.
    fireEvent.click(screen.getByRole('button', { name: /Use a different photo/i }))
    pickFile(container, new File([new Uint8Array([9, 9, 9])], 'q.png', { type: 'image/png' }))
    await screen.findByLabelText(SEED_LABEL)
    expect(URL.createObjectURL).toHaveBeenCalledTimes(2) // a fresh preview for the 2nd photo
    expect(URL.revokeObjectURL).toHaveBeenCalled() // the 1st blob URL was revoked — no leak on re-pick
  })
})
