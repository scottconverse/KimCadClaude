// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Viewport from './Viewport'

// Stub the three.js/WebGL viewport so the component renders in jsdom — we're testing the overlay,
// not the 3D scene.
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
    dispose() {}
  },
}))

afterEach(() => cleanup())

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
