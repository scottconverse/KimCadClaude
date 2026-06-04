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

  it('shows the thinking indicator while busy and hides the refine input', () => {
    renderPanel({ messages: [{ role: 'user', content: 'a box' }], busy: true, result: null })
    expect(screen.getByText(/Designing your part/i)).toBeTruthy()
    expect(screen.queryByRole('textbox', { name: /Refine your part/i })).toBeNull()
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
})

describe('ChatPanel CompareCard', () => {
  it('uses the gate vocabulary ("Passed"/"Needs review"), not the raw enum (UX-003)', () => {
    const card: CompareMessage = {
      type: 'compare',
      a: ver(1, { report: { gate_status: 'pass', headline: '', dims: [], findings: [] } }),
      b: ver(2, { report: { gate_status: 'warn', headline: '', dims: [], findings: [] } }),
    }
    renderPanel({ compareCard: card })
    expect(screen.getByText('Passed')).toBeTruthy()
    expect(screen.getByText('Needs review')).toBeTruthy()
    expect(screen.queryByText('pass')).toBeNull()
    expect(screen.queryByText('warn')).toBeNull()
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
