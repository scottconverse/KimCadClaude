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

// A completed result carrying a Smart Mesh readiness verdict (Stage 7). Uses the 'warn' tone so
// the readiness verdict ("Printable with notes") never collides with the gate badge string.
const readinessResult: DesignResponse = {
  status: 'completed',
  has_mesh: true,
  mesh_url: '/api/mesh/9',
  plan: { object_type: 'box', summary: 'a box', target_bbox_mm: [80, 60, 40] },
  report: {
    gate_status: 'warn',
    headline: '',
    dims: [],
    findings: [],
    readiness: {
      score: 72,
      verdict: 'Printable with notes',
      tone: 'warn',
      confidence: 'High',
      risks: [
        { title: 'Overhang unsupported', detail: 'A 55° overhang has no support.', tone: 'warn' },
      ],
      recommendations: [
        'Add supports under the overhang.',
        'Slice for PLA on the selected printer’s profile.',
      ],
      comparison: null,
      attribution: 'PrintProof3D validation engine',
    },
  },
}

describe('RightPanel', () => {
  it('renders the printability verdict, the size, and findings from the result', () => {
    stubFetch()
    renderPanel({ result: passResult })
    // The gate badge is framed as the technical check ("Gate: Passed"), not the readiness headline.
    expect(screen.getByText(/Gate: Passed/)).toBeTruthy()
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
    expect(screen.getByText(/generated directly/i)).toBeTruthy()
  })
})

describe('RightPanel readiness card', () => {
  it('renders the score gauge, verdict, confidence, risks, recommendations, and attribution', () => {
    stubFetch()
    renderPanel({ result: readinessResult })
    // The gauge exposes the score to assistive tech.
    expect(screen.getByRole('img', { name: /readiness score 72 out of 100/i })).toBeTruthy()
    expect(screen.getByText('Printable with notes')).toBeTruthy()
    expect(screen.getByText('High confidence')).toBeTruthy()
    // A risk (title + plain detail).
    expect(screen.getByText('Overhang unsupported')).toBeTruthy()
    expect(screen.getByText(/55° overhang/)).toBeTruthy()
    // A concrete recommendation.
    expect(screen.getByText('Add supports under the overhang.')).toBeTruthy()
    // Honest attribution of what backed the verdict.
    expect(screen.getByText(/via PrintProof3D validation engine/i)).toBeTruthy()
    // The risk's severity tier has a non-color (screen-reader) cue, not just the dot color.
    expect(screen.getByText(/Warning:/)).toBeTruthy()
  })

  it('applies the pass tone class and the honest gate-only attribution for a passing part', () => {
    stubFetch()
    const passReadiness: DesignResponse = {
      status: 'completed',
      has_mesh: true,
      mesh_url: '/api/mesh/2',
      plan: { object_type: 'box', summary: 'a box', target_bbox_mm: [80, 60, 40] },
      report: {
        gate_status: 'pass',
        headline: '',
        dims: [],
        findings: [],
        readiness: {
          score: 92,
          verdict: 'Ready to print',
          tone: 'pass',
          confidence: 'Medium',
          risks: [],
          recommendations: ['Slice for PLA on the selected printer’s profile.'],
          comparison: null,
          attribution: 'KimCad printability gate',
        },
      },
    }
    const { container } = renderPanel({ result: passReadiness })
    expect(container.querySelector('.kc-readiness.kc-rtone-pass')).toBeTruthy()
    expect(screen.getByText(/via KimCad printability gate/i)).toBeTruthy()
    expect(screen.getByText('Medium confidence')).toBeTruthy()
    // The gauge reflects the score.
    expect(screen.getByRole('img', { name: /readiness score 92 out of 100/i })).toBeTruthy()
  })

  it('renders the history comparison line when one is present', () => {
    stubFetch()
    const withHistory: DesignResponse = {
      ...readinessResult,
      report: {
        ...readinessResult.report!,
        readiness: {
          ...readinessResult.report!.readiness!,
          comparison: 'Matches your strongest past prints.',
        },
      },
    }
    renderPanel({ result: withHistory })
    expect(screen.getByText('Matches your strongest past prints.')).toBeTruthy()
  })

  it('shows the readiness placeholder before a part is designed', () => {
    stubFetch()
    renderPanel({ result: null })
    expect(screen.getByText(/print-readiness score .* appears here/i)).toBeTruthy()
  })

  it('shows a failed-attempt note (not the idle placeholder) when the design failed', () => {
    stubFetch()
    renderPanel({ result: { status: 'gate_failed', has_mesh: false } as DesignResponse })
    expect(screen.getByText(/no part to assess/i)).toBeTruthy()
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
    expect(screen.queryByText(/generated directly/i)).toBeNull()
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

  it('shows a quiet re-rendering note while a re-render is in flight', () => {
    stubFetch()
    renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
      rerendering: true,
    })
    expect(screen.getByText('Re-rendering…')).toBeTruthy()
  })

  it('hides the re-rendering note when not re-rendering (the note is purely prop-driven)', () => {
    stubFetch()
    renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
      rerendering: false,
    })
    expect(screen.queryByText('Re-rendering…')).toBeNull()
  })

  it('surfaces a re-render error with a recoverable next action and reassurance', () => {
    stubFetch()
    renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
      rerenderError: 'KimCad couldn’t re-render this part.',
    })
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toMatch(/didn.t render/i)
    expect(alert.textContent).toMatch(/last version is still here/i)
    expect(alert.textContent).toMatch(/nudge a slider to try again/i)
    // Controls are never stuck disabled after an error.
    expect((screen.getByRole('slider', { name: 'Width' }) as HTMLInputElement).disabled).toBe(false)
  })

  it('renders the per-axis chip for a dimensional slider', () => {
    stubFetch()
    renderPanel({
      result: templateResult([
        param({ name: 'width', label: 'Width', value: 80, max: 200, axis: 'X' }),
      ]),
    })
    expect(screen.getByText('X')).toBeTruthy()
  })

  it('does not fire the debounced re-render after the panel unmounts', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props, unmount } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
    })
    fireEvent.change(screen.getByRole('slider', { name: 'Width' }), { target: { value: '120' } })
    unmount()
    act(() => {
      vi.advanceTimersByTime(150)
    })
    expect(props.onRerender).not.toHaveBeenCalled()
  })

  // Slice 3: numeric editing — clicking the value display opens an inline text input.
  it('clicking the value display opens an inline numeric input (Slice 3)', () => {
    stubFetch()
    renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
    })
    // The value is shown as a clickable button initially.
    const valBtn = screen.getByRole('button', { name: /Width: 80 mm/i })
    expect(valBtn).toBeTruthy()
    fireEvent.click(valBtn)
    // After clicking, a number input replaces it.
    const numInput = screen.getByRole('spinbutton', { name: /Width value/i })
    expect(numInput).toBeTruthy()
    expect((numInput as HTMLInputElement).value).toBe('80')
  })

  it('Enter on the numeric input commits the value via the debounce (Slice 3)', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
    })
    fireEvent.click(screen.getByRole('button', { name: /Width: 80 mm/i }))
    const numInput = screen.getByRole('spinbutton', { name: /Width value/i })
    fireEvent.change(numInput, { target: { value: '120' } })
    fireEvent.keyDown(numInput, { key: 'Enter' })
    act(() => { vi.advanceTimersByTime(200) })
    expect(props.onRerender).toHaveBeenCalledWith(expect.objectContaining({ width: 120 }))
  })

  it('clamps an out-of-range numeric input to the spec bounds on commit (Slice 3)', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, min: 10, max: 200 })]),
    })
    fireEvent.click(screen.getByRole('button', { name: /Width: 80 mm/i }))
    const numInput = screen.getByRole('spinbutton', { name: /Width value/i })
    fireEvent.change(numInput, { target: { value: '500' } }) // over max
    fireEvent.keyDown(numInput, { key: 'Enter' })
    act(() => { vi.advanceTimersByTime(200) })
    // Clamped to max=200
    expect(props.onRerender).toHaveBeenCalledWith(expect.objectContaining({ width: 200 }))
  })

  it('Escape cancels the numeric input without committing (Slice 3)', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
    })
    fireEvent.click(screen.getByRole('button', { name: /Width: 80 mm/i }))
    const numInput = screen.getByRole('spinbutton', { name: /Width value/i })
    fireEvent.change(numInput, { target: { value: '999' } })
    fireEvent.keyDown(numInput, { key: 'Escape' })
    act(() => { vi.advanceTimersByTime(200) })
    expect(props.onRerender).not.toHaveBeenCalled()
    // The value button is restored
    expect(screen.getByRole('button', { name: /Width: 80 mm/i })).toBeTruthy()
  })
})
