// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { HighlightRisk } from '../viewport/KCViewport'
import Viewport from './Viewport'

// Shared spies for the highlight API so tests can assert what the wrapper forwards to the engine.
const hl = vi.hoisted(() => ({
  setHighlights: vi.fn(),
  setHighlightsVisible: vi.fn(),
  focusHighlight: vi.fn(),
}))

// Stub the three.js/WebGL viewport so the component renders in jsdom — we're testing the overlay
// + the highlight forwarding, not the 3D scene.
vi.mock('../viewport/KCViewport', () => ({
  KCViewport: class {
    loadMesh() {
      return Promise.resolve()
    }
    clearModel() {}
    getDimensions() {
      return { x: 10, y: 10, z: 10 }
    }
    captureThumbnail() {
      return null
    }
    setHighlights = hl.setHighlights
    setHighlightsVisible = hl.setHighlightsVisible
    focusHighlight = hl.focusHighlight
    dispose() {}
  },
}))

afterEach(() => cleanup())
beforeEach(() => {
  hl.setHighlights.mockClear()
  hl.setHighlightsVisible.mockClear()
  hl.focusHighlight.mockClear()
})

const baseProps = {
  meshUrl: null,
  busy: false,
  restoring: false,
  busyElapsed: 0,
  onCancelDesign: vi.fn(),
}

describe('Viewport busy overlay (escape)', () => {
  it('a design run shows the cancelable overlay: elapsed timer + honest copy + a working Cancel', () => {
    const onCancel = vi.fn()
    render(<Viewport {...baseProps} busy restoring={false} busyElapsed={75} onCancelDesign={onCancel} />)
    expect(screen.getByText(/Designing your part/i)).toBeTruthy()
    expect(screen.getByText(/1:15 elapsed/)).toBeTruthy() // fmtElapsed(75)
    expect(screen.getByText(/runs on your computer.s AI/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('a reopen (restoring) shows a plain "Reopening…" overlay — no timer, no dead Cancel (ENG-001/002)', () => {
    render(<Viewport {...baseProps} busy restoring busyElapsed={99999} />)
    expect(screen.getByText(/Reopening your design/i)).toBeTruthy()
    expect(screen.queryByText(/Designing your part/i)).toBeNull()
    expect(screen.queryByText(/elapsed/i)).toBeNull() // no garbage timer on a reopen
    expect(screen.queryByRole('button', { name: /^Cancel$/i })).toBeNull() // no dead Cancel
  })
})

describe('Viewport problem highlights (Slice 8)', () => {
  const risks: HighlightRisk[] = [
    { issueId: 'OVERHANG_UNSUPPORTED', tone: 'warn', geometry: { type: 'point', x: 0, y: 0, z: 0 } },
  ]

  it('forwards highlights + visibility to the engine', () => {
    render(<Viewport {...baseProps} meshUrl="/api/mesh/1" highlights={risks} showHighlights />)
    expect(hl.setHighlights).toHaveBeenCalledWith(risks)
    expect(hl.setHighlightsVisible).toHaveBeenLastCalledWith(true)
  })

  it('toggling visibility off forwards false', () => {
    const { rerender } = render(
      <Viewport {...baseProps} meshUrl="/api/mesh/1" highlights={risks} showHighlights />,
    )
    rerender(
      <Viewport {...baseProps} meshUrl="/api/mesh/1" highlights={risks} showHighlights={false} />,
    )
    expect(hl.setHighlightsVisible).toHaveBeenLastCalledWith(false)
  })

  it('a focus request (with a changing nonce) focuses that issue each time', () => {
    const { rerender } = render(
      <Viewport {...baseProps} meshUrl="/api/mesh/1" highlights={risks} focus={null} />,
    )
    rerender(
      <Viewport {...baseProps} meshUrl="/api/mesh/1" highlights={risks}
        focus={{ id: 'OVERHANG_UNSUPPORTED', n: 1 }} />,
    )
    expect(hl.focusHighlight).toHaveBeenLastCalledWith('OVERHANG_UNSUPPORTED')
    rerender(
      <Viewport {...baseProps} meshUrl="/api/mesh/1" highlights={risks}
        focus={{ id: 'OVERHANG_UNSUPPORTED', n: 2 }} />,
    )
    expect(hl.focusHighlight).toHaveBeenCalledTimes(2) // re-focus on a repeat click
  })
})
