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
    recordPrintOutcome: vi.fn(),
  }
})
const mockConnectors = api.getConnectors as unknown as ReturnType<typeof vi.fn>
const mockStatus = api.getConnectorStatus as unknown as ReturnType<typeof vi.fn>
const mockSend = api.sendDesign as unknown as ReturnType<typeof vi.fn>
const mockOutcome = api.recordPrintOutcome as unknown as ReturnType<typeof vi.fn>

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
    // UX-1004: the raw config key is presented in the product's register.
    const opt = (await screen.findByRole('option', {
      name: /Bambu P2S \(not set up yet\)/,
    })) as HTMLOptionElement
    expect(opt.disabled).toBe(true)
    expect(opt.value).toBe('bambu_p2s') // the VALUE stays the exact config key
  })

  it('selecting an unconfigured connection surfaces the server’s per-piece diagnosis (UX-1001)', async () => {
    mockConnectors.mockResolvedValue({
      connectors: [{ name: 'bambu_p2s', simulated: false, configured: false }],
      default: null,
    })
    mockStatus.mockResolvedValue({
      name: 'bambu_p2s', ready: false, simulated: false, reason: 'config',
      note: "The 'bambu_p2s' connection has no printer address (IP) configured.",
    })
    render(<SendPanel designId={1} />)
    // The exact missing piece, from /api/connector-status — not a generic pointer.
    expect(await screen.findByText(/no printer address \(IP\) configured/i)).toBeTruthy()
    // And the venue is the REAL Settings section (ConnectionsCard, Slice 11.2).
    expect(screen.getAllByText(/Settings → Printer connections/).length).toBeGreaterThanOrEqual(1)
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
    // UX-1006: right after OUR send, "printing" is the user's own job — progress, not "Busy".
    expect(await screen.findByText(/printing — your job is running/i)).toBeTruthy()
  })

  it('asks for the real print outcome after a hardware send and records the answer', async () => {
    mockConnectors.mockResolvedValue(REAL_AND_MOCK)
    mockSend.mockResolvedValue({ sent: true, connector: 'octoprint', simulated: false, job_id: 'j10', state: 'printing' })
    mockStatus.mockResolvedValue({
      name: 'octoprint', ready: false, online: true, state: 'printing', reason: 'busy', simulated: false,
    })
    mockOutcome.mockResolvedValue({ recorded: true })
    render(<SendPanel designId={10} />)
    fireEvent.click(await screen.findByRole('button', { name: /send to printer/i }))
    fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
    expect(await screen.findByText(/how did the print come out/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /had issues/i }))
    await waitFor(() => expect(mockOutcome).toHaveBeenCalledWith(10, 'issues'))
    expect(await screen.findByText(/thanks — saved/i)).toBeTruthy()
  })

  it('does not ask for an outcome after a simulated send', async () => {
    mockConnectors.mockResolvedValue(MOCK_ONLY)
    mockSend.mockResolvedValue({ sent: true, connector: 'mock', simulated: true, job_id: 'j1' })
    render(<SendPanel designId={11} />)
    fireEvent.click(await screen.findByRole('button', { name: /send test job/i }))
    fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
    expect(await screen.findByText(/test job accepted/i)).toBeTruthy()
    expect(screen.queryByText(/how did the print come out/i)).toBeNull()
  })

  it('unmount stops the live-status poll chain (no background polling after re-slice)', async () => {
    // TEST-1001 (stage-10 gate): fake timers are installed BEFORE render — installing
    // them after the real 5s timer was scheduled can never fire it, which made the old
    // version of this test pass even with the cleanup deleted (empirically vacuous).
    vi.useFakeTimers()
    try {
      mockConnectors.mockResolvedValue(REAL_AND_MOCK)
      mockSend.mockResolvedValue({ sent: true, connector: 'octoprint', simulated: false, job_id: 'j2' })
      mockStatus.mockResolvedValue({
        name: 'octoprint', ready: false, online: true, state: 'printing', reason: 'busy', simulated: false,
      })
      const { unmount } = render(<SendPanel designId={6} />)
      await vi.advanceTimersByTimeAsync(0) // flush the connectors load
      fireEvent.click(screen.getByRole('button', { name: /send to printer/i }))
      fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
      await vi.advanceTimersByTimeAsync(0) // send resolves; the first poll fires
      expect(mockStatus).toHaveBeenCalledTimes(1)
      // PROVE the chain is observable under these fake timers: a 5s tick polls again.
      await vi.advanceTimersByTimeAsync(5000)
      expect(mockStatus).toHaveBeenCalledTimes(2)
      unmount() // a re-slice unmounts the panel — the chain must die with it
      const callsAtUnmount = mockStatus.mock.calls.length
      await vi.advanceTimersByTimeAsync(30000) // 6 would-be poll ticks
      expect(mockStatus.mock.calls.length).toBe(callsAtUnmount)
    } finally {
      vi.useRealTimers()
    }
  })

  it('a superseding send kills the old chain — the old connector is never polled again (TEST-1001)', async () => {
    vi.useFakeTimers()
    try {
      mockConnectors.mockResolvedValue(REAL_AND_MOCK)
      mockSend.mockResolvedValue({ sent: true, connector: 'octoprint', simulated: false, job_id: 'j3' })
      mockStatus.mockResolvedValue({
        name: 'octoprint', ready: false, online: true, state: 'printing', reason: 'busy', simulated: false,
      })
      render(<SendPanel designId={8} />)
      await vi.advanceTimersByTimeAsync(0)
      fireEvent.click(screen.getByRole('button', { name: /send to printer/i }))
      fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
      await vi.advanceTimersByTimeAsync(0)
      expect(mockStatus).toHaveBeenCalledTimes(1) // the octoprint chain is live
      // Supersede: switch to the simulated connector and send again (no poll for a test job).
      mockSend.mockResolvedValue({ sent: true, connector: 'mock', simulated: true, job_id: 'j4' })
      fireEvent.change(screen.getByRole('combobox'), { target: { value: 'mock' } })
      fireEvent.click(screen.getByRole('button', { name: /send test job/i }))
      fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
      await vi.advanceTimersByTimeAsync(0)
      const callsAfterSupersede = mockStatus.mock.calls.length
      await vi.advanceTimersByTimeAsync(30000)
      // The OLD octoprint chain is dead — no further polls under the new job's banner.
      expect(mockStatus.mock.calls.length).toBe(callsAfterSupersede)
    } finally {
      vi.useRealTimers()
    }
  })

  it('one failed status poll keeps the chain alive on the bounded budget (ENG-1003)', async () => {
    vi.useFakeTimers()
    try {
      mockConnectors.mockResolvedValue(REAL_AND_MOCK)
      mockSend.mockResolvedValue({ sent: true, connector: 'octoprint', simulated: false, job_id: 'j5' })
      mockStatus
        .mockResolvedValueOnce({
          name: 'octoprint', ready: false, online: true, state: 'printing', reason: 'busy', simulated: false,
        })
        .mockRejectedValueOnce(new Error('one transient network blip'))
        .mockResolvedValue({
          name: 'octoprint', ready: true, online: true, state: 'operational', simulated: false,
        })
      render(<SendPanel designId={9} />)
      await vi.advanceTimersByTimeAsync(0)
      fireEvent.click(screen.getByRole('button', { name: /send to printer/i }))
      fireEvent.click(screen.getByRole('alertdialog').querySelector('.kc-btn-accent') as HTMLElement)
      await vi.advanceTimersByTimeAsync(0)
      expect(mockStatus).toHaveBeenCalledTimes(1) // poll 1 ok (printing)
      await vi.advanceTimersByTimeAsync(5000) // poll 2 FAILS
      expect(mockStatus).toHaveBeenCalledTimes(2)
      await vi.advanceTimersByTimeAsync(5000) // the chain survived the failure — poll 3 lands
      expect(mockStatus).toHaveBeenCalledTimes(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it('shows a visible why when every connection is unconfigured (button disabled)', async () => {
    mockConnectors.mockResolvedValue({
      connectors: [{ name: 'bambu_p2s', simulated: false, configured: false }],
      default: 'bambu_p2s',
    })
    // The unconfigured selection also fetches its per-piece status (UX-1001).
    mockStatus.mockResolvedValue({
      name: 'bambu_p2s', ready: false, simulated: false, reason: 'config', note: 'No IP configured.',
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
