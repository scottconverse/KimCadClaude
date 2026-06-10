// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Hoist-safe mock of the api module (the factory runs before module-body consts exist).
const { getSettings, postSettings, getModelStatus, getHealth, getModelPullProgress } = vi.hoisted(() => ({
  getSettings: vi.fn(),
  postSettings: vi.fn(),
  getModelStatus: vi.fn(),
  getHealth: vi.fn(),
  getModelPullProgress: vi.fn(),
}))
vi.mock('../api', () => ({ getSettings, postSettings, getModelStatus, getHealth, getModelPullProgress }))

import SettingsPanel from './SettingsPanel'

const SETTINGS = {
  printers: [
    { key: 'bambu_p2s', name: 'Bambu Lab P2S', sliceable: true, materials: ['pla'], generic_materials: [] },
    { key: 'elegoo', name: 'Elegoo Neptune 4 Max', sliceable: true, materials: ['pla'], generic_materials: [] },
  ],
  materials: [{ key: 'pla', name: 'PLA' }, { key: 'petg', name: 'PETG' }],
  default_printer: 'bambu_p2s',
  default_material: 'pla',
  cloud_enabled: false,
  cloud_model: '',
  has_cloud_key: false,
  cloud_key_masked: null,
  experimental_enabled: false,
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
  getHealth.mockResolvedValue({ version: '0.1.0', openscad: true, orcaslicer: true })
  getModelPullProgress.mockReset()
  getModelPullProgress.mockResolvedValue({ running: false, models: {} })
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

  it('describes a CLOUD model as off-machine, not "nothing leaves your computer" (UX-001)', async () => {
    // The privacy copy must track the live backend: when the effective model is cloud, the card
    // must NOT claim the on-device privacy guarantee (that would contradict the core promise).
    getModelStatus.mockResolvedValue({
      model: 'anthropic/claude', backend: 'cloud', running: true, model_present: true,
    })
    const { container } = render(<SettingsPanel />)
    // The description text spans a <code> child; assert on this render's container text after the
    // async model-status load resolves.
    await waitFor(() => expect(container.textContent).toMatch(/sent to the cloud/i))
    expect(container.textContent).not.toMatch(/nothing leaves your computer/i)
  })

  it('describes a LOCAL model as on-device', async () => {
    const { container } = render(<SettingsPanel />)  // RUNNING is backend:'local'
    await waitFor(() => expect(container.textContent).toMatch(/nothing leaves your computer/i))
    expect(container.textContent).not.toMatch(/sent to the cloud/i)
  })

  it('tells the user to start Ollama when it isn’t running', async () => {
    getModelStatus.mockResolvedValue({ ...RUNNING, running: false, model_present: false })
    render(<SettingsPanel />)
    expect(await screen.findByText('Not running')).toBeTruthy()
    expect(screen.getByText(/Ollama isn.t running/i)).toBeTruthy()
  })

  it('tells the user to get the model when Ollama is up but it isn’t installed', async () => {
    getModelStatus.mockResolvedValue({ ...RUNNING, running: true, model_present: false })
    render(<SettingsPanel />)
    expect(await screen.findByText('Model not pulled')).toBeTruthy()
    // DOC-1005 (stage-10 gate): the in-app download is the first-named path now.
    const action = screen.getByText(/isn.t downloaded yet/i)
    expect(action.textContent).toMatch(/wizard.s Download button/i)
    expect(action.textContent).toMatch(/ollama pull/i) // the manual path stays named
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

  // --- Slice 6 MS-3: the cloud opt-in section ---
  it('cloud is off by default; toggling it on posts cloud_enabled and shows the privacy label', async () => {
    render(<SettingsPanel />)
    await screen.findByLabelText(/Default printer/i)
    const sw = screen.getByRole('switch', { name: /Use a cloud model/i })
    expect(sw.getAttribute('aria-checked')).toBe('false')
    expect(screen.getByText(/sends your prompt off your machine/i)).toBeTruthy()
    postSettings.mockResolvedValue({ ...SETTINGS, cloud_enabled: true, saved: true })
    fireEvent.click(sw)
    await waitFor(() => expect(postSettings).toHaveBeenCalledWith({ cloud_enabled: true }))
  })

  it('with cloud enabled and no key, the key field + Save appear and saving posts the key', async () => {
    getSettings.mockResolvedValue({ ...SETTINGS, cloud_enabled: true, has_cloud_key: false })
    render(<SettingsPanel />)
    const keyInput = (await screen.findByLabelText('OpenRouter API key')) as HTMLInputElement
    // FOUND-001: an obscured field that opts out of browser autofill / save-password.
    expect(keyInput.type).toBe('password')
    expect(keyInput.getAttribute('autocomplete')).toBe('off')
    const save = screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement
    expect(save.disabled).toBe(true)
    fireEvent.change(keyInput, { target: { value: 'or-fake-key-12345' } })
    expect(save.disabled).toBe(false)
    postSettings.mockResolvedValue({ ...SETTINGS, cloud_enabled: true, has_cloud_key: true, cloud_key_masked: '••••••••••••••••12345', saved: true })
    fireEvent.click(save)
    await waitFor(() => expect(postSettings).toHaveBeenCalledWith({ openrouter_api_key: 'or-fake-key-12345' }))
  })

  it('with a saved key, shows it masked with a Replace button (never the raw key)', async () => {
    getSettings.mockResolvedValue({
      ...SETTINGS, cloud_enabled: true, has_cloud_key: true, cloud_key_masked: '••••••••••••••••wQ9f2',
    })
    render(<SettingsPanel />)
    expect(await screen.findByDisplayValue('••••••••••••••••wQ9f2')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Replace' })).toBeTruthy()
  })

  it('saving the model field posts cloud_model on blur', async () => {
    getSettings.mockResolvedValue({ ...SETTINGS, cloud_enabled: true, cloud_model: '' })
    render(<SettingsPanel />)
    const modelInput = await screen.findByLabelText('OpenRouter model')
    fireEvent.change(modelInput, { target: { value: 'anthropic/claude-sonnet' } })
    postSettings.mockResolvedValue({ ...SETTINGS, cloud_enabled: true, cloud_model: 'anthropic/claude-sonnet', saved: true })
    fireEvent.blur(modelInput)
    await waitFor(() => expect(postSettings).toHaveBeenCalledWith({ cloud_model: 'anthropic/claude-sonnet' }))
  })

  // --- Slice 6 MS-4: the experimental toggle ---
  it('the experimental generator is off by default and toggling it posts experimental_enabled', async () => {
    render(<SettingsPanel />)
    await screen.findByLabelText(/Default printer/i)
    const sw = screen.getByRole('switch', { name: /experimental shape generator/i })
    expect(sw.getAttribute('aria-checked')).toBe('false')
    // The "Untrusted" framing is present.
    expect(screen.getByText(/Experimental · Untrusted/i)).toBeTruthy()
    expect(screen.getByText(/offers the generator rather than running it/i)).toBeTruthy()
    postSettings.mockResolvedValue({ ...SETTINGS, experimental_enabled: true, saved: true })
    fireEvent.click(sw)
    await waitFor(() => expect(postSettings).toHaveBeenCalledWith({ experimental_enabled: true }))
  })

  // --- Slice 6 MS-5: tools health + about/reset ---
  it('shows the bundled tools as installed and the app version', async () => {
    render(<SettingsPanel />)
    expect(await screen.findByText('OpenSCAD')).toBeTruthy()
    expect(screen.getByText('OrcaSlicer')).toBeTruthy()
    expect(screen.getAllByText('Installed').length).toBe(2)
    expect(screen.getByText(/v0\.1\.0/)).toBeTruthy()
  })

  it('flags a missing tool as Not found', async () => {
    getHealth.mockResolvedValue({ version: '0.1.0', openscad: true, orcaslicer: false })
    render(<SettingsPanel />)
    expect(await screen.findByText('Not found')).toBeTruthy()
  })

  it('shows "Couldn’t check" when the health fetch fails (not a perpetual Checking…)', async () => {
    getHealth.mockRejectedValue(new Error('boom'))
    render(<SettingsPanel />)
    await screen.findByLabelText(/Default printer/i)
    await waitFor(() => expect(screen.getAllByText(/Couldn.t check/i).length).toBeGreaterThanOrEqual(1))
  })

  it('Reset can be cancelled without changing anything', async () => {
    render(<SettingsPanel />)
    fireEvent.click(await screen.findByRole('button', { name: 'Reset…' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    // Back to the single Reset… button; nothing posted.
    expect(screen.getByRole('button', { name: 'Reset…' })).toBeTruthy()
    expect(postSettings).not.toHaveBeenCalled()
  })

  // --- Slice 10.4: the vision-model row (Stage 9 watchlist #3) -------------------------

  it('shows the vision row as downloaded when the second model is present', async () => {
    getModelStatus.mockResolvedValue({
      ...RUNNING, vision_model: 'qwen2.5vl:3b', vision_present: true,
    })
    render(<SettingsPanel />)
    expect(await screen.findByText(/Photo & sketch reader/)).toBeTruthy()
    expect(screen.getByText(/downloaded\./)).toBeTruthy()
  })

  it('a missing vision model gets the pull command + wizard pointer, not silence', async () => {
    getModelStatus.mockResolvedValue({
      ...RUNNING, vision_model: 'qwen2.5vl:3b', vision_present: false,
    })
    render(<SettingsPanel />)
    expect(await screen.findByText(/photos and sketches won’t work yet/i)).toBeTruthy()
    expect(screen.getByText(/ollama pull qwen2\.5vl:3b/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /check again/i })).toBeTruthy()
  })

  it('says NOTHING about vision when the fields are absent (unknown ≠ missing)', async () => {
    getModelStatus.mockResolvedValue(RUNNING) // no vision fields (e.g. unknowable in-band)
    render(<SettingsPanel />)
    await screen.findByText(/KimCad’s local AI/)
    expect(screen.queryByText(/Photo & sketch reader/)).toBeNull()
  })

  it('an in-flight in-app download shows as downloading — never a competing manual pull (UX-1002)', async () => {
    getModelStatus.mockResolvedValue({
      ...RUNNING, vision_model: 'qwen2.5vl:3b', vision_present: false,
    })
    getModelPullProgress.mockResolvedValue({
      running: true,
      models: { 'qwen2.5vl:3b': { status: 'pulling', completed: 800, total: 1000, error: '' } },
    })
    render(<SettingsPanel />)
    expect(await screen.findByText(/downloading now \(80%\)/i)).toBeTruthy()
    // The competing-manual-pull suggestion must NOT show while the download runs.
    expect(screen.queryByText(/ollama pull qwen2\.5vl:3b/)).toBeNull()
  })

  it('Reset asks to confirm, then clears settings + units to defaults', async () => {
    localStorage.setItem('kc-units', 'in')
    render(<SettingsPanel />)
    fireEvent.click(await screen.findByRole('button', { name: 'Reset…' }))
    // Confirm step appears (not a one-click destructive action).
    const confirm = screen.getByRole('button', { name: 'Reset everything' })
    postSettings.mockResolvedValue({ ...SETTINGS, saved: true })
    fireEvent.click(confirm)
    // A full reset clears everything server-side (pristine) + resets client units.
    await waitFor(() => expect(postSettings).toHaveBeenCalledWith({ reset: true }))
    expect(localStorage.getItem('kc-units')).toBe('mm')
  })
})

describe('SettingsPanel key-storage disclosure + Remove (stage-BCD TEST-002 / DOC-D-001)', () => {
  it('discloses the credential store when key_storage is keyring', async () => {
    getSettings.mockResolvedValue({ ...SETTINGS, cloud_enabled: true, key_storage: 'keyring' })
    render(<SettingsPanel />)
    expect(await screen.findByText(/secure credential store/i)).toBeTruthy()
    expect(screen.queryByText(/settings file on this computer/i)).toBeNull()
  })

  it('discloses the file fallback honestly (with the risk sentence) when key_storage is file', async () => {
    getSettings.mockResolvedValue({ ...SETTINGS, cloud_enabled: true, key_storage: 'file' })
    render(<SettingsPanel />)
    expect(await screen.findByText(/settings file on this computer/i)).toBeTruthy()
    expect(screen.getByText(/could read it/i)).toBeTruthy()
  })

  it('Remove deletes the saved key via the settings endpoint', async () => {
    getSettings.mockResolvedValue({
      ...SETTINGS, cloud_enabled: true, has_cloud_key: true,
      cloud_key_masked: '****wQ9f2', key_storage: 'keyring',
    })
    postSettings.mockResolvedValue({ ...SETTINGS, cloud_enabled: true, has_cloud_key: false, saved: true })
    render(<SettingsPanel />)
    fireEvent.click(await screen.findByRole('button', { name: /^Remove$/ }))
    await waitFor(() =>
      expect(postSettings).toHaveBeenCalledWith({ openrouter_api_key: null }),
    )
  })
})
