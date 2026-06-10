// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import FirstRunWizard from './FirstRunWizard'

vi.mock('../api', () => ({
  getSettings: vi.fn().mockResolvedValue({
    printers: [
      { key: 'p1', name: 'Printer One', sliceable: true, materials: [], generic_materials: [] },
      { key: 'p2', name: 'Printer Two', sliceable: false, materials: [], generic_materials: [] },
    ],
    materials: [],
    default_printer: 'p1',
    default_material: null,
    cloud_enabled: false,
  }),
  getModelStatus: vi.fn().mockResolvedValue({
    model: 'gemma4:e4b',
    backend: 'local',
    running: true,
    model_present: true,
  }),
  postSettings: vi.fn().mockResolvedValue({ saved: true }),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function go(name: RegExp) {
  fireEvent.click(screen.getByRole('button', { name }))
}

describe('FirstRunWizard', () => {
  it('opens on the welcome step and Skip setup calls onClose', () => {
    const onClose = vi.fn()
    render(<FirstRunWizard onClose={onClose} />)
    expect(screen.getByText('Welcome to KimCad')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /skip setup/i }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('shows gemma4:e4b as THE design model with its health — no alternative chat model offered', async () => {
    const { container } = render(<FirstRunWizard onClose={vi.fn()} />)
    go(/continue/i) // → Your AI model
    expect(await screen.findByText('gemma4:e4b')).toBeTruthy()
    // The model health is "Ready" (running + present) — scoped to the status element so it doesn't
    // collide with the rail's step-5 label, also named "Ready".
    expect(container.querySelector('.kc-wiz-model-stat')?.textContent).toMatch(/Ready/)
    // Trust rule 1: the wizard never offers an ALTERNATIVE chat model (the Stage-6-rejected
    // qwen2.5-coder, or any menu of choices). The Stage 9 vision model (qwen2.5vl:3b) is a
    // companion for reading images, not an alternative — its mention is allowed.
    expect(screen.queryByText(/qwen2\.5-coder/i)).toBeNull()
    expect(container.querySelectorAll('.kc-wiz-modelcard').length).toBe(1) // ONE model card
  })

  it('persists the chosen printer via the settings endpoint', async () => {
    const api = await import('../api')
    render(<FirstRunWizard onClose={vi.fn()} />)
    go(/continue/i) // model
    go(/continue/i) // printer
    await screen.findByText('Printer One')
    fireEvent.click(screen.getByRole('button', { name: /Printer Two/i }))
    expect(api.postSettings).toHaveBeenCalledWith({ default_printer: 'p2' })
  })

  it('finishing saves an opted-in cloud key and calls onClose', async () => {
    const api = await import('../api')
    const onClose = vi.fn()
    render(<FirstRunWizard onClose={onClose} />)
    go(/continue/i) // model step
    await screen.findByText('gemma4:e4b')
    fireEvent.click(screen.getByLabelText(/Add an OpenRouter key/i))
    fireEvent.change(screen.getByLabelText('OpenRouter API key'), { target: { value: 'sk-or-abc' } })
    go(/continue/i) // printer
    go(/continue/i) // direct printing
    go(/continue/i) // ready
    fireEvent.click(screen.getByRole('button', { name: /start designing/i }))
    await waitFor(() =>
      expect(api.postSettings).toHaveBeenCalledWith(
        expect.objectContaining({ cloud_enabled: true, openrouter_api_key: 'sk-or-abc' }),
      ),
    )
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('traps Tab focus inside the dialog (a11y modal)', () => {
    render(<FirstRunWizard onClose={vi.fn()} />)
    const dialog = screen.getByRole('dialog')
    const sel =
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(sel))
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    last.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(document.activeElement).toBe(first) // wraps forward
    first.focus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last) // wraps backward
  })

  it('recap does not claim "+ OpenRouter" for a key without a model (honest)', async () => {
    render(<FirstRunWizard onClose={vi.fn()} />)
    go(/continue/i) // model
    await screen.findByText('gemma4:e4b')
    fireEvent.click(screen.getByLabelText(/Add an OpenRouter key/i))
    fireEvent.change(screen.getByLabelText('OpenRouter API key'), { target: { value: 'sk-or-x' } })
    go(/continue/i) // printer
    go(/continue/i) // direct
    go(/continue/i) // ready
    // The recap model reads plain gemma4:e4b — an exact match proves no "+ OpenRouter" suffix was
    // appended (cloud isn't usable without a model slug, so the recap must not imply it is).
    expect(screen.getByText('gemma4:e4b')).toBeTruthy()
  })

  it('recap says "You’re all set" only when the model is actually ready (UX-002)', async () => {
    render(<FirstRunWizard onClose={vi.fn()} />)
    go(/continue/i) // model
    go(/continue/i) // printer
    go(/continue/i) // direct
    go(/continue/i) // ready
    expect(await screen.findByText('You’re all set')).toBeTruthy()
    expect(screen.queryByText('Almost ready')).toBeNull()
  })

  it('recap demotes to "Almost ready" with a fix + re-check when Ollama is down (UX-002)', async () => {
    const api = await import('../api')
    ;(api.getModelStatus as ReturnType<typeof vi.fn>).mockResolvedValue({
      model: 'gemma4:e4b',
      backend: 'local',
      running: false,
      model_present: false,
    })
    render(<FirstRunWizard onClose={vi.fn()} />)
    go(/continue/i) // model
    go(/continue/i) // printer
    go(/continue/i) // direct
    go(/continue/i) // ready
    expect(await screen.findByText('Almost ready')).toBeTruthy()
    expect(screen.queryByText('You’re all set')).toBeNull()
    // The recap row carries the cause + an in-place re-check; finishing stays possible.
    expect(screen.getByText(/not reachable yet — start Ollama/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /check again/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /start designing/i })).toBeTruthy()
  })

  it('recap names the pull command when Ollama runs but the model is absent (UX-002)', async () => {
    const api = await import('../api')
    ;(api.getModelStatus as ReturnType<typeof vi.fn>).mockResolvedValue({
      model: 'gemma4:e4b',
      backend: 'local',
      running: true,
      model_present: false,
    })
    render(<FirstRunWizard onClose={vi.fn()} />)
    go(/continue/i)
    go(/continue/i)
    go(/continue/i)
    go(/continue/i)
    expect(await screen.findByText('Almost ready')).toBeTruthy()
    expect(screen.getByText(/ollama pull gemma4:e4b/)).toBeTruthy()
  })

  it('Escape skips setup (calls onClose)', () => {
    const onClose = vi.fn()
    render(<FirstRunWizard onClose={onClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('is an accessible modal dialog labelled by the step heading', () => {
    render(<FirstRunWizard onClose={vi.fn()} />)
    const dialog = screen.getByRole('dialog')
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    // the labelledby points at the visible step heading
    const labelId = dialog.getAttribute('aria-labelledby')
    expect(labelId && document.getElementById(labelId)?.textContent).toMatch(/Welcome to KimCad/)
  })
})
