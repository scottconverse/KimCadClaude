// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi, type Mock } from 'vitest'
import type { DesignResponse } from './api'
import App from './App'

// Mock the API so we control the design + re-render timing without a server.
vi.mock('./api', () => ({
  postDesign: vi.fn(),
  postRender: vi.fn(),
  // App only needs a non-null id to proceed with a re-render.
  designIdFromMeshUrl: () => 1,
}))

// Replace the (three.js) Workspace so the test doesn't pull in WebGL. The stub exposes the
// `rerendering` flag and a button that triggers a re-render, which is all this test inspects.
vi.mock('./components/Workspace', () => ({
  default: ({
    rerendering,
    onRerender,
  }: {
    rerendering: boolean
    onRerender: (values: Record<string, number>) => void
  }) => (
    <div>
      <span data-testid="rerendering">{String(rerendering)}</span>
      <button type="button" onClick={() => onRerender({ width: 1 })}>
        do-rerender
      </button>
    </div>
  ),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function templateResult(meshUrl: string): DesignResponse {
  return {
    status: 'completed',
    has_mesh: true,
    mesh_url: meshUrl,
    template: 'snap_box',
    plan: { object_type: 'snap_box', summary: 'a snap box', target_bbox_mm: [80, 60, 40] },
    report: { gate_status: 'pass', headline: '', dims: [], findings: [] },
    parameters: [
      { name: 'width', label: 'Width', value: 80, min: 10, max: 250, step: 1, unit: 'mm', integer: false },
    ],
  }
}

async function designFrom(prompt: string) {
  fireEvent.change(screen.getByLabelText(/describe the part/i), { target: { value: prompt } })
  fireEvent.click(screen.getByRole('button', { name: /design it/i }))
  // The workspace is lazy-loaded; wait for the (mocked) stub to mount.
  return screen.findByTestId('rerendering')
}

describe('App live-slider lifecycle', () => {
  it('clears the re-render flag when a new design abandons an in-flight re-render', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock)
      .mockResolvedValueOnce(templateResult('/api/mesh/1'))
      .mockResolvedValueOnce(templateResult('/api/mesh/1?v=9'))
    // The re-render never resolves — so the ONLY thing that can clear `rerendering` is App's
    // explicit reset on the new-design path. That isolates the SLIDE-001 fix.
    ;(api.postRender as Mock).mockReturnValue(new Promise<DesignResponse>(() => {}))

    render(<App />)

    const flag = await designFrom('a box')
    expect(flag.textContent).toBe('false')

    // Kick off a re-render → the flag goes true and stays true (the promise is pending).
    fireEvent.click(screen.getByRole('button', { name: 'do-rerender' }))
    expect(screen.getByTestId('rerendering').textContent).toBe('true')

    // Abandon it via "New design", then start a fresh design.
    fireEvent.click(screen.getByRole('button', { name: /new design/i }))
    const flag2 = await designFrom('a different box')

    // Without the fix the abandoned re-render leaves the flag stuck true on the new design.
    expect(flag2.textContent).toBe('false')
  })
})
