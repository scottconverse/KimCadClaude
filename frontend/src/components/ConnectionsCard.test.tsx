// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ConnectionsCard from './ConnectionsCard'
import * as api from '../api'

// Stage 11 Slice 11.2 — the Connections card. Contracts: real connections only (the mock
// loopback never shows); the secret never renders (only its env var's NAME + set/not-set);
// Save POSTs exactly the editable fields; the per-piece note shows for an unconfigured row.
vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return { ...actual, getConnections: vi.fn(), saveConnection: vi.fn() }
})
const mockGet = api.getConnections as unknown as ReturnType<typeof vi.fn>
const mockSave = api.saveConnection as unknown as ReturnType<typeof vi.fn>

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const LISTING = {
  connections: [
    {
      name: 'mock', type: 'loopback', simulated: true, configured: true, note: '',
      base_url: '', serial: '', use_ams: true, api_key_env: '', env_set: false,
    },
    {
      name: 'bambu_p2s', type: 'bambu', simulated: false, configured: false,
      note: "The 'bambu_p2s' connection has no printer address (IP) configured.",
      base_url: '', serial: '', use_ams: true,
      api_key_env: 'BAMBU_P2S_ACCESS_CODE', env_set: false,
    },
    {
      name: 'octoprint', type: 'octoprint', simulated: false, configured: true, note: '',
      base_url: 'http://octopi.local', serial: '', use_ams: true,
      api_key_env: 'OCTOPRINT_API_KEY', env_set: true,
    },
  ],
}

describe('ConnectionsCard', () => {
  it('lists REAL connections only, with the per-piece note and env-var guidance', async () => {
    mockGet.mockResolvedValue(LISTING)
    render(<ConnectionsCard />)
    expect(await screen.findByText('Bambu P2S')).toBeTruthy()
    expect(screen.getByText('Octoprint')).toBeTruthy()
    expect(screen.queryByText(/^Mock$/)).toBeNull() // the loopback never shows here
    // The exact missing piece, from the server.
    expect(screen.getByText(/no printer address \(IP\) configured/)).toBeTruthy()
    // The secret's VENUE: the env var named, a setx line offered when unset…
    expect(screen.getByText('BAMBU_P2S_ACCESS_CODE')).toBeTruthy()
    expect(screen.getByText(/setx BAMBU_P2S_ACCESS_CODE/)).toBeTruthy()
    // …and "set ✓" (no setx nag) when it is set.
    expect(screen.queryByText(/setx OCTOPRINT_API_KEY/)).toBeNull()
  })

  it('Save POSTs exactly the editable fields (serial only for bambu)', async () => {
    mockGet.mockResolvedValue(LISTING)
    mockSave.mockResolvedValue({ saved: true })
    render(<ConnectionsCard />)
    await screen.findByText('Bambu P2S')
    fireEvent.change(screen.getByLabelText('Printer address', { selector: '#conn-url-bambu_p2s' }), {
      target: { value: '192.168.0.60' },
    })
    fireEvent.change(screen.getByLabelText('Serial number'), { target: { value: '01S00C123' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Save' })[0])
    await waitFor(() =>
      expect(mockSave).toHaveBeenCalledWith('bambu_p2s', {
        base_url: '192.168.0.60',
        serial: '01S00C123',
        use_ams: true,
      }),
    )
    expect(await screen.findByText('Saved.')).toBeTruthy()
    expect(mockGet).toHaveBeenCalledTimes(2) // re-read the effective verdicts
  })

  it('the AMS toggle flips and is included in the save; octoprint has no serial field', async () => {
    mockGet.mockResolvedValue(LISTING)
    mockSave.mockResolvedValue({ saved: true })
    render(<ConnectionsCard />)
    await screen.findByText('Bambu P2S')
    fireEvent.click(screen.getByRole('switch', { name: /feed from the ams/i }))
    fireEvent.click(screen.getAllByRole('button', { name: 'Save' })[0])
    await waitFor(() =>
      expect(mockSave).toHaveBeenCalledWith('bambu_p2s', expect.objectContaining({ use_ams: false })),
    )
    // Octoprint's row: address yes, serial/AMS no.
    expect(screen.getAllByLabelText('Printer address').length).toBe(2)
    expect(screen.getAllByLabelText('Serial number').length).toBe(1)
  })

  it('an HTTP-family save gets a scheme and never the Bambu-only fields (M-1/N-4)', async () => {
    mockGet.mockResolvedValue(LISTING)
    mockSave.mockResolvedValue({ saved: true })
    render(<ConnectionsCard />)
    await screen.findByText('Octoprint')
    fireEvent.change(screen.getByLabelText('Printer address', { selector: '#conn-url-octoprint' }), {
      target: { value: 'octopi.local' }, // bare host — the scheme is added on save
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Save' })[1]) // octoprint's row
    await waitFor(() =>
      expect(mockSave).toHaveBeenCalledWith('octoprint', { base_url: 'http://octopi.local' }),
    )
  })

  it('a failed save reads honestly; a failed LIST shows a retry, never a dead end (N-2)', async () => {
    mockGet.mockResolvedValue(LISTING)
    mockSave.mockRejectedValue(new Error('boom'))
    render(<ConnectionsCard />)
    await screen.findByText('Bambu P2S')
    fireEvent.click(screen.getAllByRole('button', { name: 'Save' })[0])
    expect(await screen.findByText(/couldn’t save — try again/i)).toBeTruthy()
    cleanup()
    // The send flow points at this card — a silent disappearance would be a dead end.
    mockGet.mockRejectedValue(new Error('down'))
    render(<ConnectionsCard />)
    expect(await screen.findByText(/couldn’t load your printer connections/i)).toBeTruthy()
    mockGet.mockResolvedValue(LISTING)
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(await screen.findByText('Bambu P2S')).toBeTruthy()
  })
})
