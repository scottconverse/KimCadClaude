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

describe('ModelHealthPill (UX-002)', () => {
  it('stays silent when the local AI is ready', async () => {
    const fn = await mockStatus(READY)
    render(<ModelHealthPill />)
    await waitFor(() => expect(fn).toHaveBeenCalled())
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('warns with a start-Ollama line when nothing is running', async () => {
    await mockStatus({ ...READY, running: false, model_present: false })
    render(<ModelHealthPill />)
    expect(await screen.findByRole('status')).toBeTruthy()
    expect(screen.getByText(/start Ollama/)).toBeTruthy()
  })

  it('warns with the exact pull command when the model is absent', async () => {
    await mockStatus({ ...READY, model_present: false })
    render(<ModelHealthPill />)
    expect(await screen.findByText(/ollama pull gemma4:e4b/)).toBeTruthy()
  })

  it('stays silent for a cloud backend and when the probe itself fails', async () => {
    await mockStatus({ ...READY, backend: 'cloud', running: false })
    const { unmount } = render(<ModelHealthPill />)
    await waitFor(async () =>
      expect((await import('../api')).getModelStatus).toHaveBeenCalled(),
    )
    expect(screen.queryByRole('status')).toBeNull()
    unmount()

    await mockStatus(new Error('no server'))
    render(<ModelHealthPill />)
    await waitFor(async () =>
      expect((await import('../api')).getModelStatus).toHaveBeenCalled(),
    )
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('Check again re-probes and clears the pill once the model comes up', async () => {
    const api = await import('../api')
    const fn = api.getModelStatus as ReturnType<typeof vi.fn>
    fn.mockResolvedValueOnce({ ...READY, running: false }) // first probe: down
    fn.mockResolvedValueOnce(READY) // re-check: up
    render(<ModelHealthPill />)
    expect(await screen.findByText(/start Ollama/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /check again/i }))
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull())
    expect(fn).toHaveBeenCalledTimes(2)
  })
})
