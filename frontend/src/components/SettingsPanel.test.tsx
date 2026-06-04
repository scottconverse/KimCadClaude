// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Hoist-safe mock of the api module (the factory runs before module-body consts exist).
const { getSettings, postSettings, getModelStatus } = vi.hoisted(() => ({
  getSettings: vi.fn(),
  postSettings: vi.fn(),
  getModelStatus: vi.fn(),
}))
vi.mock('../api', () => ({ getSettings, postSettings, getModelStatus }))

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

const RUNNING = { model: 'gemma4:e4b', backend: 'local', running: true, model_present: true }

beforeEach(() => {
  localStorage.clear()
  getSettings.mockReset()
  postSettings.mockReset()
  getModelStatus.mockReset()
  getSettings.mockResolvedValue(SETTINGS)
  postSettings.mockResolvedValue({ ...SETTINGS, default_printer: 'elegoo', saved: true })
  getModelStatus.mockResolvedValue(RUNNING)
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

  // --- Slice 6 MS-2: the AI model status section ---
  it('shows the model as Running (Local) when Ollama is up with the model pulled', async () => {
    render(<SettingsPanel />)
    expect(await screen.findByText('Running')).toBeTruthy()
    expect(screen.getByText('Local')).toBeTruthy()
    // gemma4:e4b is shown as THE model; there is no model dropdown/menu of alternatives.
    expect(screen.getByText('gemma4:e4b')).toBeTruthy()
    expect(screen.queryByRole('combobox', { name: /model/i })).toBeNull()
  })

  it('tells the user to start Ollama when it isn’t running', async () => {
    getModelStatus.mockResolvedValue({ ...RUNNING, running: false, model_present: false })
    render(<SettingsPanel />)
    expect(await screen.findByText('Not running')).toBeTruthy()
    expect(screen.getByText(/Ollama isn.t running/i)).toBeTruthy()
  })

  it('tells the user to pull the model when Ollama is up but it isn’t installed', async () => {
    getModelStatus.mockResolvedValue({ ...RUNNING, running: true, model_present: false })
    render(<SettingsPanel />)
    expect(await screen.findByText('Model not pulled')).toBeTruthy()
    expect(screen.getByText(/isn.t pulled yet/i)).toBeTruthy()
  })

  it('Refresh re-checks the model status', async () => {
    render(<SettingsPanel />)
    await screen.findByText('Running')
    expect(getModelStatus).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(getModelStatus).toHaveBeenCalledTimes(2))
  })

  it('shows "Couldn’t check" when the model status request fails', async () => {
    getModelStatus.mockRejectedValue(new Error('boom'))
    render(<SettingsPanel />)
    expect(await screen.findByText(/Couldn.t check/i)).toBeTruthy()
  })
})
