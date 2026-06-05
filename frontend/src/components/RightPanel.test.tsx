// @vitest-environment jsdom
import type { ComponentProps } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DesignResponse, ParamSpec } from '../api'
import RightPanel from './RightPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.useRealTimers()
  // Slice 4: the units preference is persisted in localStorage — clear it so a test that
  // switches to inches can't leak that choice into the mm-assuming tests that follow.
  localStorage.clear()
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

  it('shows the idle placeholder (not a Size readout) for the experimental-offer state (MS-4)', () => {
    stubFetch()
    renderPanel({
      result: {
        status: 'needs_experimental',
        has_mesh: false,
        plan: { object_type: 'coaster', summary: 'a coaster', target_bbox_mm: [80, 60, 40] },
      } as DesignResponse,
    })
    // No sliders, and no "Size"/bbox readout implying a part exists.
    expect(screen.queryAllByRole('slider')).toHaveLength(0)
    expect(screen.queryByText(/80 × 60 × 40/)).toBeNull()
    expect(screen.queryByText(/generated directly/i)).toBeNull()
    expect(screen.getByText(/parameters will appear here/i)).toBeTruthy()
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

  it('makes a located risk clickable (focus) and offers a show-on-model toggle (Slice 8)', () => {
    stubFetch()
    const located: DesignResponse = {
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
            {
              title: 'Overhang unsupported',
              detail: 'A 55° overhang has no support.',
              tone: 'warn',
              issueId: 'OVERHANG_UNSUPPORTED',
              region: 'overhangs',
              geometry: { type: 'point', x: 0, y: 0, z: 0 },
            },
          ],
          recommendations: [],
          comparison: null,
          attribution: 'PrintProof3D validation engine',
        },
      },
    }
    const onFocusRisk = vi.fn()
    const onToggleHighlights = vi.fn()
    renderPanel({ result: located, onFocusRisk, highlightsOn: true, onToggleHighlights })
    // The located risk is a button; clicking it asks the viewport to focus that issue.
    fireEvent.click(screen.getByRole('button', { name: /Overhang unsupported/i }))
    expect(onFocusRisk).toHaveBeenCalledWith('OVERHANG_UNSUPPORTED')
    // The "Show on model" toggle drives the on-model overlay.
    fireEvent.click(screen.getByLabelText(/Show on model/i))
    expect(onToggleHighlights).toHaveBeenCalledTimes(1)
  })

  it('renders a non-located risk as plain text (no button, no toggle) when no geometry', () => {
    stubFetch()
    renderPanel({ result: readinessResult, onFocusRisk: vi.fn(), onToggleHighlights: vi.fn() })
    // readinessResult's risk has no geometry → not a button, and no "Show on model" toggle.
    expect(screen.queryByRole('button', { name: /Overhang unsupported/i })).toBeNull()
    expect(screen.queryByLabelText(/Show on model/i)).toBeNull()
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

// Slice 4 — mm / inch units. The backend always works in mm; the unit toggle only changes the
// display + the unit numbers are entered in. Every onRerender call must still emit mm.
describe('RightPanel units (Slice 4)', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('defaults to mm and offers a mm/in toggle', () => {
    stubFetch()
    renderPanel({ result: passResult })
    const mmBtn = screen.getByRole('button', { name: 'mm' })
    const inBtn = screen.getByRole('button', { name: 'in' })
    expect(mmBtn.getAttribute('aria-pressed')).toBe('true')
    expect(inBtn.getAttribute('aria-pressed')).toBe('false')
    // Default size is shown in mm.
    expect(screen.getByText(/80 × 60 × 40 mm/)).toBeTruthy()
  })

  it('switching to inches converts the size readout and the unit label', () => {
    stubFetch()
    renderPanel({ result: passResult })
    fireEvent.click(screen.getByRole('button', { name: 'in' }))
    // 80/60/40 mm → 3.15/2.362/1.575 in (3dp, trailing zeros trimmed — UX-004).
    expect(screen.getByText(/3\.15 × 2\.362 × 1\.575 in/)).toBeTruthy()
    expect(screen.queryByText(/80 × 60 × 40 mm/)).toBeNull()
    expect(screen.getByRole('button', { name: 'in' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('converts the printability dims table header and cells to inches', () => {
    stubFetch()
    renderPanel({ result: passResult })
    fireEvent.click(screen.getByRole('button', { name: 'in' }))
    // Column headers now read "(in)".
    expect(screen.getByRole('columnheader', { name: /Target \(in\)/ })).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: /Actual \(in\)/ })).toBeTruthy()
    // The 80mm target/actual cells convert to 3.15.
    expect(screen.getAllByText('3.15').length).toBeGreaterThanOrEqual(2)
  })

  it('converts a slider value display and its aria-valuetext to inches', () => {
    stubFetch()
    renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
    })
    fireEvent.click(screen.getByRole('button', { name: 'in' }))
    // The value label is now "3.15 in" and the slider announces inches.
    expect(screen.getByRole('button', { name: /Width: 3\.15 in/i })).toBeTruthy()
    const slider = screen.getByRole('slider', { name: 'Width' })
    expect(slider.getAttribute('aria-valuetext')).toBe('3.15 in')
  })

  it('a numeric edit entered in inches commits the mm-converted value', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, min: 10, max: 200 })]),
    })
    fireEvent.click(screen.getByRole('button', { name: 'in' }))
    // Open the inline input (seeded with 3.15 in) and type a fresh inch value.
    fireEvent.click(screen.getByRole('button', { name: /Width: 3\.15 in/i }))
    const numInput = screen.getByRole('spinbutton', { name: /Width value in inches/i })
    fireEvent.change(numInput, { target: { value: '4' } }) // 4 in → 101.6 mm
    fireEvent.keyDown(numInput, { key: 'Enter' })
    act(() => { vi.advanceTimersByTime(200) })
    expect(props.onRerender).toHaveBeenCalledTimes(1)
    const emitted = vi.mocked(props.onRerender).mock.calls[0][0] as Record<string, number>
    // The backend still receives mm, not inches.
    expect(emitted.width).toBeCloseTo(101.6, 5)
  })

  it('an out-of-range inch entry clamps to the mm spec bounds', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, min: 10, max: 200 })]),
    })
    fireEvent.click(screen.getByRole('button', { name: 'in' }))
    fireEvent.click(screen.getByRole('button', { name: /Width: 3\.15 in/i }))
    const numInput = screen.getByRole('spinbutton', { name: /Width value in inches/i })
    fireEvent.change(numInput, { target: { value: '40' } }) // 40 in → 1016 mm, over max 200
    fireEvent.keyDown(numInput, { key: 'Enter' })
    act(() => { vi.advanceTimersByTime(200) })
    expect(props.onRerender).toHaveBeenCalledTimes(1)
    const emitted = vi.mocked(props.onRerender).mock.calls[0][0] as Record<string, number>
    expect(emitted.width).toBe(200) // clamped to the mm max
  })

  it('restores the persisted inch preference on mount', () => {
    stubFetch()
    localStorage.setItem('kc-units', 'in')
    renderPanel({ result: passResult })
    expect(screen.getByRole('button', { name: 'in' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText(/3\.15 × 2\.362 × 1\.575 in/)).toBeTruthy()
  })

  // FOUND-001: opening the inch editor and committing the unchanged (2dp-rounded) seed must NOT
  // drift the mm value or fire a re-render — the value reads identically, so it's a no-op.
  it('does not re-render when an inch numeric edit is committed unchanged', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, min: 10, max: 200 })]),
    })
    fireEvent.click(screen.getByRole('button', { name: 'in' }))
    // 80mm shows as 3.15in. Open the editor and commit without changing the seeded value.
    fireEvent.click(screen.getByRole('button', { name: /Width: 3\.15 in/i }))
    const numInput = screen.getByRole('spinbutton', { name: /Width value in inches/i })
    expect((numInput as HTMLInputElement).value).toBe('3.15') // seeded from the rounded display
    fireEvent.keyDown(numInput, { key: 'Enter' })
    act(() => { vi.advanceTimersByTime(200) })
    // No drift to 80.01mm, no wasted re-render.
    expect(props.onRerender).not.toHaveBeenCalled()
  })

  it('still re-renders when an inch numeric edit is a real change', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, min: 10, max: 200 })]),
    })
    fireEvent.click(screen.getByRole('button', { name: 'in' }))
    fireEvent.click(screen.getByRole('button', { name: /Width: 3\.15 in/i }))
    const numInput = screen.getByRole('spinbutton', { name: /Width value in inches/i })
    fireEvent.change(numInput, { target: { value: '3.5' } }) // 3.5in → 88.9mm, a real change
    fireEvent.keyDown(numInput, { key: 'Enter' })
    act(() => { vi.advanceTimersByTime(200) })
    expect(props.onRerender).toHaveBeenCalledTimes(1)
    const emitted = vi.mocked(props.onRerender).mock.calls[0][0] as Record<string, number>
    expect(emitted.width).toBeCloseTo(88.9, 5)
  })

  // TEST-003: one toggle click must convert BOTH a slider value (ParametersCard) AND the dims
  // table (PrintabilityCard) — the two are separate useUnits() instances; this proves the shared
  // store keeps them in lockstep (a plain-useState refactor would regress this green).
  it('a single toggle converts both the slider value and the dims table together', () => {
    stubFetch()
    const both: DesignResponse = {
      status: 'completed',
      has_mesh: true,
      mesh_url: '/api/mesh/5',
      template: 'snap_box',
      plan: { object_type: 'snap_box', summary: 'a snap box', target_bbox_mm: [80, 60, 40] },
      report: {
        gate_status: 'pass',
        headline: '',
        dims: [{ axis: 'X', target: 80, actual: 80, ok: true }],
        findings: [],
      },
      parameters: [param({ name: 'width', label: 'Width', value: 80, max: 200 })],
    }
    renderPanel({ result: both })
    // mm first: slider value 80 mm, dims cell 80.
    expect(screen.getByRole('button', { name: /Width: 80 mm/i })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'in' }))
    // After ONE click: slider value 3.15 in AND the dims target/actual cells read 3.15.
    expect(screen.getByRole('button', { name: /Width: 3\.15 in/i })).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: /Target \(in\)/ })).toBeTruthy()
    expect(screen.getAllByText('3.15').length).toBeGreaterThanOrEqual(2)
  })

  // TEST-004: an empty or non-numeric numeric edit reverts with no change (no onRerender).
  it('reverts an empty or non-numeric numeric edit without re-rendering', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([param({ name: 'width', label: 'Width', value: 80, max: 200 })]),
    })
    fireEvent.click(screen.getByRole('button', { name: /Width: 80 mm/i }))
    const numInput = screen.getByRole('spinbutton', { name: /Width value/i })
    fireEvent.change(numInput, { target: { value: '' } }) // cleared
    fireEvent.keyDown(numInput, { key: 'Enter' })
    act(() => { vi.advanceTimersByTime(200) })
    expect(props.onRerender).not.toHaveBeenCalled()
    // The original value button is restored.
    expect(screen.getByRole('button', { name: /Width: 80 mm/i })).toBeTruthy()
  })

  // ENG-002: a real sub-0.1 mm typed change in mm mode must commit, not be swallowed by the no-op guard.
  it('commits a sub-0.1 mm change in mm mode (not swallowed by the no-op guard)', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([
        param({ name: 'wall', label: 'Wall', value: 2, min: 0.8, max: 8, step: 0.1 }),
      ]),
    })
    fireEvent.click(screen.getByRole('button', { name: /Wall: 2 mm/i }))
    const numInput = screen.getByRole('spinbutton', { name: /Wall value/i })
    fireEvent.change(numInput, { target: { value: '2.04' } })
    fireEvent.keyDown(numInput, { key: 'Enter' })
    act(() => { vi.advanceTimersByTime(200) })
    expect(props.onRerender).toHaveBeenCalledTimes(1)
    const emitted = vi.mocked(props.onRerender).mock.calls[0][0] as Record<string, number>
    expect(emitted.wall).toBeCloseTo(2.04, 5)
  })

  // TEST-005: an integer-spec param rounds on commit (the Math.round branch in clampToSpec/format).
  it('rounds a typed value for an integer-spec parameter', () => {
    stubFetch()
    vi.useFakeTimers()
    const { props } = renderPanel({
      result: templateResult([
        param({ name: 'teeth', label: 'Teeth', value: 12, min: 4, max: 40, step: 1, integer: true }),
      ]),
    })
    // Integer display shows no decimals.
    fireEvent.click(screen.getByRole('button', { name: /Teeth: 12/i }))
    const numInput = screen.getByRole('spinbutton', { name: /Teeth value/i })
    fireEvent.change(numInput, { target: { value: '18.7' } })
    fireEvent.keyDown(numInput, { key: 'Enter' })
    act(() => { vi.advanceTimersByTime(200) })
    expect(props.onRerender).toHaveBeenCalledTimes(1)
    const emitted = vi.mocked(props.onRerender).mock.calls[0][0] as Record<string, number>
    expect(emitted.teeth).toBe(19) // 18.7 rounded to the nearest integer
  })
})
