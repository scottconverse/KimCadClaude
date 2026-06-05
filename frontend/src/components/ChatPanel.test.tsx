// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CompareMessage, DesignResponse, DesignVersion, Message } from '../api'
import ChatPanel from './ChatPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear() // CompareCard reads the units preference
})

const completed: DesignResponse = {
  status: 'completed',
  has_mesh: true,
  mesh_url: '/api/mesh/1',
  plan: { object_type: 'box', summary: 'a box', target_bbox_mm: [80, 60, 40] },
}

function renderPanel(overrides: Partial<React.ComponentProps<typeof ChatPanel>> = {}) {
  const props = {
    messages: [] as Message[],
    compareCard: null as CompareMessage | null,
    result: completed as DesignResponse | null,
    busy: false,
    error: null as string | null,
    onRefine: vi.fn(),
    onTryExperimental: vi.fn(),
    onPhotoSeed: vi.fn(),
    ...overrides,
  }
  return { ...render(<ChatPanel {...props} />), props }
}

function ver(index: number, over: Partial<DesignResponse>): DesignVersion {
  return {
    index,
    messages: [],
    result: { status: 'completed', has_mesh: true, mesh_url: `/api/mesh/${index}`, ...over },
    label: `v${index}`,
  }
}

describe('ChatPanel thread', () => {
  it('renders user and assistant turns in order', () => {
    renderPanel({
      messages: [
        { role: 'user', content: 'a 80mm box' },
        { role: 'assistant', content: 'Here you go — a box.' },
      ],
    })
    expect(screen.getByText('a 80mm box')).toBeTruthy()
    expect(screen.getByText('Here you go — a box.')).toBeTruthy()
  })

  it('UX-008: on a first design (no part yet) the refine input is hidden and the duplicate "Designing" row is suppressed', () => {
    renderPanel({ messages: [{ role: 'user', content: 'a box' }], busy: true, result: null })
    // The viewport's full overlay owns the progress on a first design — no duplicate chat row.
    expect(screen.queryByText(/Designing your part/i)).toBeNull()
    expect(screen.queryByRole('textbox', { name: /Refine your part/i })).toBeNull()
  })

  it('UX-008: shows an in-thread "Refining" row when busy with a part already on screen', () => {
    renderPanel({ messages: [{ role: 'user', content: 'a box' }], busy: true, result: completed })
    expect(screen.getByText(/Refining your part/i)).toBeTruthy()
  })

  it('shows the refine input once there is a result', () => {
    renderPanel({ messages: [{ role: 'assistant', content: 'done' }] })
    expect(screen.getByRole('textbox', { name: /Refine your part/i })).toBeTruthy()
  })

  it('Enter submits the refinement; Shift+Enter does not', () => {
    const { props } = renderPanel({ messages: [{ role: 'assistant', content: 'done' }] })
    const box = screen.getByRole('textbox', { name: /Refine your part/i })
    fireEvent.change(box, { target: { value: 'make it taller' } })
    fireEvent.keyDown(box, { key: 'Enter', shiftKey: true })
    expect(props.onRefine).not.toHaveBeenCalled()
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(props.onRefine).toHaveBeenCalledWith('make it taller')
  })

  it('disables Send when the input is empty', () => {
    renderPanel({ messages: [{ role: 'assistant', content: 'done' }] })
    const send = screen.getByRole('button', { name: /Send refinement/i }) as HTMLButtonElement
    expect(send.disabled).toBe(true)
    fireEvent.change(screen.getByRole('textbox', { name: /Refine your part/i }), {
      target: { value: 'x' },
    })
    expect(send.disabled).toBe(false)
  })

  it('swaps the placeholder to answer-the-question on a clarification', () => {
    renderPanel({
      messages: [{ role: 'assistant', content: 'How tall?' }],
      result: { status: 'clarification_needed', has_mesh: false, clarification: 'How tall?' },
    })
    const box = screen.getByRole('textbox', { name: /Refine your part/i }) as HTMLTextAreaElement
    expect(box.placeholder).toMatch(/Answer the question above/i)
  })

  // --- Slice 6 MS-4: the experimental-generator offer ---
  it('offers the experimental generator on needs_experimental and Try calls onTryExperimental', () => {
    const { props } = renderPanel({
      messages: [{ role: 'assistant', content: "I don't have a precise template for that." }],
      result: { status: 'needs_experimental', has_mesh: false },
    })
    expect(screen.getByText(/Experimental · may not be perfect/i)).toBeTruthy()
    const tryBtn = screen.getByRole('button', { name: /Try the experimental generator/i })
    fireEvent.click(tryBtn)
    expect(props.onTryExperimental).toHaveBeenCalledTimes(1)
  })

  it('offers a one-click Try again on model_unavailable and it calls onRetry (Slice 9 MS-1)', () => {
    const onRetry = vi.fn()
    const { props } = renderPanel({
      messages: [{ role: 'assistant', content: "Your local AI isn't running. Start Ollama…" }],
      result: { status: 'model_unavailable', has_mesh: false },
      onRetry,
    })
    fireEvent.click(screen.getByRole('button', { name: /Try again/i }))
    expect(props.onRetry).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/Settings/i)).toBeTruthy() // points to where to check Ollama status
  })

  it('does not show the experimental offer for a normal completed result', () => {
    renderPanel({ result: completed })
    expect(screen.queryByRole('button', { name: /Try the experimental generator/i })).toBeNull()
  })
})

describe('ChatPanel CompareCard', () => {
  it('uses the gate vocabulary ("Passed"/"Needs review"), not the raw enum (UX-003)', () => {
    const card: CompareMessage = {
      type: 'compare',
      a: ver(1, { report: { gate_status: 'pass', headline: '', dims: [], findings: [] } }),
      b: ver(2, { report: { gate_status: 'warn', headline: '', dims: [], findings: [] } }),
    }
    const { container } = renderPanel({ compareCard: card })
    expect(screen.getByText('Passed')).toBeTruthy()
    expect(screen.getByText('Needs review')).toBeTruthy()
    expect(screen.queryByText('pass')).toBeNull()
    expect(screen.queryByText('warn')).toBeNull()
    // Both chips use the gate tone class (not a mismatched kc-tone-* token) so they paint consistently.
    const chips = container.querySelectorAll('.kc-compare-gate')
    expect(chips).toHaveLength(2)
    chips.forEach((c) => expect(c.className).toMatch(/kc-gate-(pass|warn|fail|neutral)/))
  })

  it('surfaces the dimensional + readiness delta (UX-006)', () => {
    const card: CompareMessage = {
      type: 'compare',
      a: ver(1, {
        plan: { object_type: 'box', summary: 'a box', target_bbox_mm: [80, 60, 40] },
        report: { gate_status: 'pass', headline: '', dims: [], findings: [], readiness: {
          score: 90, verdict: '', tone: 'pass', confidence: 'High', risks: [], recommendations: [],
          comparison: null, attribution: '',
        } },
      }),
      b: ver(2, {
        plan: { object_type: 'box', summary: 'a taller box', target_bbox_mm: [80, 60, 52] },
        report: { gate_status: 'pass', headline: '', dims: [], findings: [], readiness: {
          score: 88, verdict: '', tone: 'pass', confidence: 'High', risks: [], recommendations: [],
          comparison: null, attribution: '',
        } },
      }),
    }
    renderPanel({ compareCard: card })
    expect(screen.getByText(/What changed/i)).toBeTruthy()
    // Height (3rd axis) changed 40 → 52 mm.
    expect(screen.getByText(/H 40 → 52 mm/)).toBeTruthy()
    expect(screen.getByText(/Readiness 90 → 88/)).toBeTruthy()
  })

  it('says "no dimensional change" when the two versions match', () => {
    const card: CompareMessage = {
      type: 'compare',
      a: ver(1, { plan: { object_type: 'box', summary: 'a box', target_bbox_mm: [80, 60, 40] } }),
      b: ver(2, { plan: { object_type: 'box', summary: 'a box', target_bbox_mm: [80, 60, 40] } }),
    }
    renderPanel({ compareCard: card })
    expect(screen.getByText(/No dimensional change/i)).toBeTruthy()
  })
})
