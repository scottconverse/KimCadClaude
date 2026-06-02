// @vitest-environment jsdom
import type { ComponentProps } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DesignResponse, ParamSpec } from '../api'
import RightPanel from './RightPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

// RightPanel embeds ExportPanel, which fetches /api/options + /api/connectors on mount — stub
// fetch so those effects resolve quietly (the assertions below are on the synchronous render).
function stubFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (String(url).includes('/api/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            printers: [
              { key: 'p', name: 'P', sliceable: true, materials: ['pla'], generic_materials: [] },
            ],
            materials: [{ key: 'pla', name: 'PLA' }],
            default_printer: 'p',
            default_material: 'pla',
          }),
        }
      }
      return { ok: true, status: 200, json: async () => ({ connectors: [], default: null }) }
    }),
  )
}

// Default the Stage 5 slider props so each test only states what it cares about.
function renderPanel(overrides: Partial<ComponentProps<typeof RightPanel>> = {}) {
  const props = {
    result: null as DesignResponse | null,
    rerendering: false,
    rerenderError: null as string | null,
    onRerender: vi.fn(),
    ...overrides,
  }
  return { ...render(<RightPanel {...props} />), props }
}

const passResult: DesignResponse = {
  status: 'completed',
  has_mesh: true,
  mesh_url: '/api/mesh/1',
  plan: { object_type: 'box', summary: 'a box', target_bbox_mm: [80, 60, 40] },
  report: {
    gate_status: 'pass',
    headline: 'Dimensions match the request',
    dims: [{ axis: 'X', target: 80, actual: 80, ok: true }],
    findings: [{ level: 'pass', code: 'dim', message: 'Dimensions match' }],
  },
}

function param(over: Partial<ParamSpec> & { name: string; label: string }): ParamSpec {
  return { value: 0, min: 0, max: 100, step: 1, unit: 'mm', integer: false, ...over }
}

function templateResult(parameters: ParamSpec[]): DesignResponse {
  return {
    status: 'completed',
    has_mesh: true,
    mesh_url: '/api/mesh/3',
    template: 'snap_box',
    plan: { object_type: 'snap_box', summary: 'a snap box', target_bbox_mm: [80, 60, 40] },
    report: { gate_status: 'pass', headline: '', dims: [], findings: [] },
    parameters,
  }
}

describe('RightPanel', () => {
  it('renders the printability verdict, the size, and findings from the result', () => {
    stubFetch()
    renderPanel({ result: passResult })
    expect(screen.getByText('Ready to print')).toBeTruthy()
    expect(screen.getByText('Dimensions match')).toBeTruthy()
    expect(screen.getByText(/80 × 60 × 40 mm/)).toBeTruthy()
  })

  it('shows placeholders when there is no result yet', () => {
    stubFetch()
    renderPanel({ result: null })
    expect(screen.getByText(/parameters will appear here/i)).toBeTruthy()
    expect(screen.getByText(/printability check .* appears here/i)).toBeTruthy()
  })

  it('shows a read-only note (no sliders) for an LLM-backed part with no parameters', () => {
    stubFetch()
    renderPanel({ result: passResult })
    expect(screen.queryAllByRole('slider')).toHaveLength(0)
    expect(screen.getByText(/written by the model/i)).toBeTruthy()
  })
})

describe('RightPanel live sliders', () => {
  it('renders one slider per backend parameter for a template-backed design', () => {
    stubFetch()
    renderPanel({
      result: templateResult([
        param({ name: 'width', label: 'Width', value: 80, max: 200 }),
        param({ name: 'height', label: 'Height', value: 40, max: 200 }),
      ]),
    })
    const sliders = screen.getAllByRole('slider')
    expect(sliders).toHaveLength(2)
    expect(screen.getByRole('slider', { name: 'Width' })).toBeTruthy()
    expect(screen.getByRole('slider', { name: 'Height' })).toBeTruthy()
    // The drag hint replaces the read-only note.
    expect(screen.getByText(/re-renders locally/i)).toBeTruthy()
    expect(screen.queryByText(/written by the model/i)).toBeNull()
  })

  it('calls onRerender with the merged values after the debounce settles', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([
        param({ name: 'width', label: 'Width', value: 80, max: 200 }),
        param({ name: 'height', label: 'Height', value: 40, max: 200 }),
      ]),
    })
    fireEvent.change(screen.getByRole('slider', { name: 'Width' }), { target: { value: '120' } })
    // Nothing fires until the debounce elapses.
    expect(props.onRerender).not.toHaveBeenCalled()
    act(() => {
      vi.advanceTimersByTime(150)
    })
    expect(props.onRerender).toHaveBeenCalledTimes(1)
    expect(props.onRerender).toHaveBeenCalledWith({ width: 120, height: 40 })
  })

  it('coalesces a rapid drag into a single re-render with the latest value', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
    })
    const slider = screen.getByRole('slider', { name: 'Width' })
    fireEvent.change(slider, { target: { value: '90' } })
    fireEvent.change(slider, { target: { value: '110' } })
    fireEvent.change(slider, { target: { value: '150' } })
    act(() => {
      vi.advanceTimersByTime(150)
    })
    expect(props.onRerender).toHaveBeenCalledTimes(1)
    expect(props.onRerender).toHaveBeenCalledWith({ width: 150 })
  })

  it('re-syncs the sliders to the server-returned (clamped) values', () => {
    stubFetch()
    const { rerender } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
    })
    expect((screen.getByRole('slider', { name: 'Width' }) as HTMLInputElement).value).toBe('80')
    // The server clamps the requested value to 150 and echoes it back as the new truth.
    rerender(
      <RightPanel
        result={templateResult([param({ name: 'width', label: 'Width', value: 150, max: 200 })])}
        rerendering={false}
        rerenderError={null}
        onRerender={vi.fn()}
      />,
    )
    expect((screen.getByRole('slider', { name: 'Width' }) as HTMLInputElement).value).toBe('150')
  })

  it('announces the value with its unit via aria-valuetext', () => {
    stubFetch()
    renderPanel({
      result: templateResult([
        param({ name: 'wall', label: 'Wall thickness', value: 2, min: 0.8, max: 8, step: 0.1 }),
      ]),
    })
    const slider = screen.getByRole('slider', { name: 'Wall thickness' })
    expect(slider.getAttribute('aria-valuetext')).toBe('2 mm')
  })

  it('shows a quiet updating note while a re-render is in flight', () => {
    stubFetch()
    renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
      rerendering: true,
    })
    expect(screen.getByText('Updating…')).toBeTruthy()
  })

  it('hides the updating note when not re-rendering (the note is purely prop-driven)', () => {
    stubFetch()
    renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
      rerendering: false,
    })
    expect(screen.queryByText('Updating…')).toBeNull()
  })

  it('surfaces a re-render error with a recoverable next action', () => {
    stubFetch()
    renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
      rerenderError: 'KimCad couldn’t re-render this part.',
    })
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toMatch(/couldn.t re-render/i)
    expect(alert.textContent).toMatch(/adjust a slider to try again/i)
    // Controls are never stuck disabled after an error.
    expect((screen.getByRole('slider', { name: 'Width' }) as HTMLInputElement).disabled).toBe(false)
  })
})
