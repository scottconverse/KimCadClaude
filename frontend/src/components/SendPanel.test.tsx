// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SendPanel from './SendPanel'
import * as api from '../api'

// Stage 10 Slice 10.2 — the direct-print panel. Contracts under test: hidden without
// connectors; honest simulated/unconfigured labeling; the send fires ONLY through the app's
// confirm dialog (never auto-starts); a soft not-sent outcome surfaces the typed note + next
// step with the download fallback named; a real send follows the printer's live status.
vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return {
    ...actual,
    getConnectors: vi.fn(),
    getConnectorStatus: vi.fn(),
    sendDesign: vi.fn(),
  }
})
const mockConnectors = api.getConnectors as unknown as ReturnType<typeof vi.fn>
const mockStatus = api.getConnectorStatus as unknown as ReturnType<typeof vi.fn>
const mockSend = api.sendDesign as unknown as ReturnType<typeof vi.fn>

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const MOCK_ONLY = {
  connectors: [{ name: 'mock', simulated: true, configured: true }],
  default: 'mock',
}
const REAL_AND_MOCK = {
  connectors: [
    { name: 'mock', simulated: true, configured: true },
    { name: 'octoprint', simulated: false, configured: true },
    { name: 'bambu_p2s', simulated: false, configured: false },
  ],
  default: 'octoprint',
}

describe('SendPanel', () => {
  it('renders nothing when there are no connectors (or the list fails)', async () => {
    mockConnectors.mockResolvedValue({ connectors: [], default: null })
    const { container } = render(<SendPanel designId={1} />)
    await waitFor(() => expect(mockConnectors).toHaveBeenCalled())
    expect(container.querySelector('.kc-send-panel')).toBeNull()

    mockConnectors.mockRejectedValue(new Error('down'))
    const { container: c2 } = render(<SendPanel designId={1} />)
    await waitFor(() => expect(mockConnectors).toHaveBeenCalledTimes(2))
    expect(c2.querySelector('.kc-send-panel')).toBeNull()
  })

  it('labels a simulated connection honestly and never narrates it as a real print', async () => {
    mockConnectors.mockResolvedValue(MOCK_ONLY)
    render(<SendPanel designId={1} />)
    expect(await screen.findByText(/test connection — no real printer/i)).toBeTruthy()
    // The action itself says "test job", not "print".
    expect(screen.getByRole('button', { name: /send test job/i })).toBeTruthy()
    expect(screen.getByText(/proves the send path without driving any hardware/i)).toBeTruthy()
  })

  it('offers an unconfigured real connector disabled, with the reason', async () => {
    mockConnectors.mockResolvedValue(REAL_AND_MOCK)
    render(<SendPanel designId={1} />)
    const opt = (await screen.findByRole('option', {
      name: /bambu_p2s \(not set up yet/i,
    })) as HTMLOptionElement
    expect(opt.disabled).toBe(true)
  })

  it('sends ONLY after the confirm dialog is confirmed — cancel sends nothing', async () => {
    mockConnectors.mockResolvedValue(MOCK_ONLY)
    mockSend.mockResolvedValue({ sent: true, connector: 'mock', simulated: true, job_id: 'j1' })
    render(<SendPanel designId={7} />)
    fireEvent.click(await screen.findByRole('button', { name: /send test job/i }))
    // The dialog is up; nothing sent yet.
    expect(mockSend).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /keep working/i }))
    expect(mockSend).not.toHaveBeenCalled()
    // Again, this time confirming.
    fireEvent.click(screen.getByRole('button', { name: /send test job/i }))
    fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
    await waitFor(() => expect(mockSend).toHaveBeenCalledWith(7, 'mock'))
    expect(await screen.findByText(/test job accepted .* no hardware ran/i)).toBeTruthy()
  })

  it('a soft not-sent outcome shows the typed note + hint and names the download fallback', async () => {
    mockConnectors.mockResolvedValue(REAL_AND_MOCK)
    mockSend.mockResolvedValue({
      sent: false,
      simulated: false,
      reason: 'offline',
      note: 'The printer connection didn’t answer.',
    })
    render(<SendPanel designId={3} />)
    fireEvent.click(await screen.findByRole('button', { name: /send to printer/i }))
    fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
    const msg = await screen.findByText(/didn’t answer/i)
    expect(msg.textContent).toMatch(/powered on and reachable/i) // the offline next step
    expect(msg.textContent).toMatch(/still downloadable/i) // download fallback named
  })

  it('a real send reports the job and follows the live printer status', async () => {
    mockConnectors.mockResolvedValue(REAL_AND_MOCK)
    mockSend.mockResolvedValue({ sent: true, connector: 'octoprint', simulated: false, job_id: 'j9', state: 'printing' })
    mockStatus.mockResolvedValue({
      name: 'octoprint', ready: false, online: true, state: 'printing', reason: 'busy', simulated: false,
    })
    render(<SendPanel designId={5} />)
    fireEvent.click(await screen.findByRole('button', { name: /send to printer/i }))
    fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
    expect(await screen.findByText(/job sent to “octoprint” \(job j9\)/i)).toBeTruthy()
    await waitFor(() => expect(mockStatus).toHaveBeenCalledWith('octoprint'))
    expect(await screen.findByText(/busy — printing/i)).toBeTruthy()
  })

  it('unmount stops the live-status poll chain (no background polling after re-slice)', async () => {
    mockConnectors.mockResolvedValue(REAL_AND_MOCK)
    mockSend.mockResolvedValue({ sent: true, connector: 'octoprint', simulated: false, job_id: 'j2' })
    mockStatus.mockResolvedValue({
      name: 'octoprint', ready: false, online: true, state: 'printing', reason: 'busy', simulated: false,
    })
    const { unmount } = render(<SendPanel designId={6} />)
    fireEvent.click(await screen.findByRole('button', { name: /send to printer/i }))
    fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
    await waitFor(() => expect(mockStatus).toHaveBeenCalledTimes(1))
    unmount() // a re-slice unmounts the panel — the chain must die with it
    const callsAtUnmount = mockStatus.mock.calls.length
    vi.useFakeTimers()
    await vi.advanceTimersByTimeAsync(30000) // 6 would-be poll ticks
    vi.useRealTimers()
    expect(mockStatus.mock.calls.length).toBe(callsAtUnmount)
  })

  it('shows a visible why when every connection is unconfigured (button disabled)', async () => {
    mockConnectors.mockResolvedValue({
      connectors: [{ name: 'bambu_p2s', simulated: false, configured: false }],
      default: 'bambu_p2s',
    })
    render(<SendPanel designId={1} />)
    expect(await screen.findByText(/none of these printer connections is set up yet/i)).toBeTruthy()
    const btn = screen.getByRole('button', { name: /send to printer/i }) as HTMLButtonElement
    expect(btn.disabled).toBe(true)
    // The picker still shows the connector (not a blank select).
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('bambu_p2s')
  })

  it('a transport failure surfaces a readable error, not a blank panel', async () => {
    mockConnectors.mockResolvedValue(MOCK_ONLY)
    mockSend.mockRejectedValue(new Error('KimCad returned an unreadable response (HTTP 500).'))
    render(<SendPanel designId={2} />)
    fireEvent.click(await screen.findByRole('button', { name: /send test job/i }))
    fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
    expect(await screen.findByText(/unreadable response/i)).toBeTruthy()
  })
})
