// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Hoist-safe mock of the api module (the factory runs before the consts exist).
const { getConnectors, getConnectorStatus } = vi.hoisted(() => ({
  getConnectors: vi.fn(),
  getConnectorStatus: vi.fn(),
}))
vi.mock('../api', () => ({ getConnectors, getConnectorStatus }))

import ConnectorStatus from './ConnectorStatus'

beforeEach(() => {
  getConnectors.mockReset()
  getConnectorStatus.mockReset()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('ConnectorStatus', () => {
  // UX-001 (b4 audit): the default mock connector must render as a plain product name with a
  // connection-describing label — never the raw config key "mock", and never "Ready · simulated".
  it('prettifies the built-in mock connector and describes the connection (not the slice)', async () => {
    getConnectors.mockResolvedValue({ connectors: [{ name: 'mock', simulated: true, configured: true }], default: 'mock' })
    getConnectorStatus.mockResolvedValue({ name: 'mock', ready: true, simulated: true })
    const { container } = render(<ConnectorStatus />)
    expect(await screen.findByText('Built-in preview')).toBeTruthy()
    expect(await screen.findByText('No printer connected')).toBeTruthy()
    // The raw key never leaks, and the ambiguous "simulated"/"Ready" wording is gone.
    expect(container.textContent).not.toMatch(/mock/i)
    expect(container.textContent).not.toMatch(/simulated/i)
    expect(container.textContent).not.toMatch(/ready/i)
  })

  it('prettifies a real connector key and shows Ready for connected hardware', async () => {
    getConnectors.mockResolvedValue({ connectors: [{ name: 'bambu_p2s', simulated: false, configured: true }], default: 'bambu_p2s' })
    getConnectorStatus.mockResolvedValue({ name: 'bambu_p2s', ready: true, simulated: false })
    const { container } = render(<ConnectorStatus />)
    expect(await screen.findByText('Bambu P2S')).toBeTruthy()
    expect(await screen.findByText('Ready')).toBeTruthy()
    expect(container.textContent).not.toMatch(/bambu_p2s/)
  })

  it('renders nothing when no connector is configured', async () => {
    getConnectors.mockResolvedValue({ connectors: [], default: null })
    const { container } = render(<ConnectorStatus />)
    await waitFor(() => expect(getConnectors).toHaveBeenCalled())
    expect(container.querySelector('.kc-connector')).toBeNull()
  })
})
