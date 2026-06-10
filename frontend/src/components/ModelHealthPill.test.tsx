// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ModelHealthPill from './ModelHealthPill'

vi.mock('../api', () => ({
  getModelStatus: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

async function mockStatus(status: object | Error) {
  const api = await import('../api')
  const fn = api.getModelStatus as ReturnType<typeof vi.fn>
  if (status instanceof Error) fn.mockRejectedValue(status)
  else fn.mockResolvedValue(status)
  return fn
}

const READY = { model: 'gemma4:e4b', backend: 'local', running: true, model_present: true }

// UX-A-002 (stage-A gate): the live region is PERSISTENTLY mounted — "silent" means the
// region carries no visible warn content, not that it unmounts (mount-with-content live
// regions announce unreliably). These tests assert the region's text, not its existence.
function pillWarn() {
  return document.querySelector('.kc-model-pill')
}

describe('ModelHealthPill (UX-002 / UX-A-001/002)', () => {
  it('shows no warning when the local AI is ready (region mounted, empty)', async () => {
    const fn = await mockStatus(READY)
    render(<ModelHealthPill />)
    await waitFor(() => expect(fn).toHaveBeenCalled())
    expect(pillWarn()).toBeNull()
    const region = screen.getByRole('status')
    expect(region.textContent).toBe('') // no spurious announcement on a healthy mount
  })

  it('warns with a start-Ollama line when nothing is running', async () => {
    await mockStatus({ ...READY, running: false, model_present: false })
    render(<ModelHealthPill />)
    await waitFor(() => expect(pillWarn()).not.toBeNull())
    expect(screen.getByText(/start Ollama/)).toBeTruthy()
  })

  it('warns with the exact pull command when the model is absent', async () => {
    await mockStatus({ ...READY, model_present: false })
    render(<ModelHealthPill />)
    expect(await screen.findByText(/ollama pull gemma4:e4b/)).toBeTruthy()
  })

  it('shows no warning for a cloud backend or when the probe itself fails', async () => {
    await mockStatus({ ...READY, backend: 'cloud', running: false })
    const { unmount } = render(<ModelHealthPill />)
    await waitFor(async () =>
      expect((await import('../api')).getModelStatus).toHaveBeenCalled(),
    )
    expect(pillWarn()).toBeNull()
    unmount()

    await mockStatus(new Error('no server'))
    render(<ModelHealthPill />)
    await waitFor(async () =>
      expect((await import('../api')).getModelStatus).toHaveBeenCalled(),
    )
    expect(pillWarn()).toBeNull()
  })

  it('Check again re-probes without unmounting under the finger, then announces recovery', async () => {
    const api = await import('../api')
    const fn = api.getModelStatus as ReturnType<typeof vi.fn>
    fn.mockResolvedValueOnce({ ...READY, running: false }) // first probe: down
    let resolveRecheck: (v: object) => void = () => {}
    fn.mockReturnValueOnce(new Promise((r) => { resolveRecheck = r })) // re-check: in flight
    render(<ModelHealthPill />)
    expect(await screen.findByText(/start Ollama/)).toBeTruthy()

    const btn = screen.getByRole('button', { name: /check again/i })
    btn.focus()
    fireEvent.click(btn)
    // UX-A-001: while the re-check is in flight the button STAYS MOUNTED (relabeled,
    // aria-disabled) and keeps focus — it must not vanish under the user's finger.
    const checking = screen.getByRole('button', { name: /checking/i })
    expect(checking.getAttribute('aria-disabled')).toBe('true')
    expect(document.activeElement).toBe(checking)
    fireEvent.click(checking) // no-op while in flight
    expect(fn).toHaveBeenCalledTimes(2)

    resolveRecheck(READY)
    // UX-A-002: recovery is ANNOUNCED — the persistent region's text flips to "ready".
    await waitFor(() => expect(pillWarn()).toBeNull())
    expect(screen.getByRole('status').textContent).toMatch(/ready/i)
  })
})
