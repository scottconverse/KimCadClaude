// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Hoist-safe mock of the api module (the factory runs before module-body consts exist).
const { getSettings, postSettings } = vi.hoisted(() => ({
  getSettings: vi.fn(),
  postSettings: vi.fn(),
}))
vi.mock('../api', () => ({ getSettings, postSettings }))

import SettingsPanel from './SettingsPanel'

const SETTINGS = {
  printers: [
    { key: 'bambu_p2s', name: 'Bambu Lab P2S', sliceable: true, materials: ['pla'], generic_materials: [] },
    { key: 'elegoo', name: 'Elegoo Neptune 4 Max', sliceable: true, materials: ['pla'], generic_materials: [] },
  ],
  materials: [{ key: 'pla', name: 'PLA' }, { key: 'petg', name: 'PETG' }],
  default_printer: 'bambu_p2s',
  default_material: 'pla',
}

beforeEach(() => {
  localStorage.clear()
  getSettings.mockReset()
  postSettings.mockReset()
  getSettings.mockResolvedValue(SETTINGS)
  postSettings.mockResolvedValue({ ...SETTINGS, default_printer: 'elegoo', saved: true })
})

afterEach(() => {
  cleanup()
  localStorage.clear()
})

describe('SettingsPanel', () => {
  it('renders the saved printer/material defaults and the units toggle', async () => {
    render(<SettingsPanel />)
    const printer = (await screen.findByLabelText(/Default printer/i)) as HTMLSelectElement
    expect(printer.value).toBe('bambu_p2s')
    const material = screen.getByLabelText(/Default material/i) as HTMLSelectElement
    expect(material.value).toBe('pla')
    // The Elegoo option is present (so the user can switch to it).
    expect(screen.getByRole('option', { name: /Elegoo Neptune 4 Max/i })).toBeTruthy()
    // Units toggle present; mm active by default.
    expect(screen.getByRole('button', { name: 'mm' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('persists a printer change and shows Saved', async () => {
    render(<SettingsPanel />)
    const printer = await screen.findByLabelText(/Default printer/i)
    fireEvent.change(printer, { target: { value: 'elegoo' } })
    await waitFor(() => expect(postSettings).toHaveBeenCalledWith({ default_printer: 'elegoo' }))
    expect(await screen.findByText('Saved')).toBeTruthy()
  })

  it('reports an honest error when the store could not persist (saved:false)', async () => {
    postSettings.mockResolvedValue({ ...SETTINGS, saved: false })
    render(<SettingsPanel />)
    const material = await screen.findByLabelText(/Default material/i)
    fireEvent.change(material, { target: { value: 'petg' } })
    expect(await screen.findByText(/didn.t stick/i)).toBeTruthy()
  })

  it('toggles units mm <-> in and persists the preference', async () => {
    render(<SettingsPanel />)
    await screen.findByLabelText(/Default printer/i)
    fireEvent.click(screen.getByRole('button', { name: 'in' }))
    expect(screen.getByRole('button', { name: 'in' }).getAttribute('aria-pressed')).toBe('true')
    expect(localStorage.getItem('kc-units')).toBe('in')
  })

  it('shows an error state if settings fail to load', async () => {
    getSettings.mockRejectedValue(new Error('network'))
    render(<SettingsPanel />)
    expect(await screen.findByRole('alert')).toBeTruthy()
    // No selects rendered when the load failed.
    expect(screen.queryByLabelText(/Default printer/i)).toBeNull()
  })
})
