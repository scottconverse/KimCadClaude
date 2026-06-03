// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi, type Mock } from 'vitest'
import type { DesignResponse } from './api'
import App from './App'

// Mock the API so we control the design + re-render timing without a server.
vi.mock('./api', () => ({
  postDesign: vi.fn(),
  postRender: vi.fn(),
  reopenDesign: vi.fn(),
  saveDesign: vi.fn().mockResolvedValue({ id: 'x', name: 'n' }),
  // App only needs a non-null id to proceed with a re-render.
  designIdFromMeshUrl: () => 1,
}))

// Replace the (three.js) Workspace so the test doesn't pull in WebGL. The stub exposes the
// `rerendering` flag and a button that triggers a re-render, which is all this test inspects.
vi.mock('./components/Workspace', () => ({
  default: ({
    rerendering,
    onRerender,
    onModelReady,
    result,
  }: {
    rerendering: boolean
    onRerender: (values: Record<string, number>) => void
    onModelReady: (capture: () => string | null) => void
    result: DesignResponse | null
  }) => (
    <div>
      <span data-testid="rerendering">{String(rerendering)}</span>
      <span data-testid="mesh-url">{result?.mesh_url ?? ''}</span>
      <button type="button" onClick={() => onRerender({ width: 1 })}>
        do-rerender
      </button>
      {/* TEST-001: stand in for the viewport firing onModelReady after it frames a part, which is
          what drives auto-save. The real Workspace omitted this from the stub, leaving persist()
          dark; here we expose it so the auto-save lifecycle can be exercised. */}
      <button type="button" onClick={() => onModelReady(() => 'data:image/png;base64,AA')}>
        frame-model
      </button>
    </div>
  ),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  window.location.hash = '' // don't leak a route into the next test
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

  it('discards a stale (out-of-order) re-render response so the newer one wins', async () => {
    // TEST-002: render A (slow) and render B (fast) both fire; B resolves first, A resolves last.
    // The renderSeq guard must drop A's late result so the viewport doesn't snap back to a stale
    // shape. Manually-resolved promises keep the ordering deterministic (no timers).
    const api = await import('./api')
    ;(api.postDesign as Mock).mockResolvedValueOnce(templateResult('/api/mesh/1'))
    const resolvers: Array<(v: DesignResponse) => void> = []
    ;(api.postRender as Mock).mockImplementation(
      () => new Promise<DesignResponse>((resolve) => resolvers.push(resolve)),
    )

    render(<App />)
    await designFrom('a box')

    // Two overlapping re-renders: A (first) then B (second).
    fireEvent.click(screen.getByRole('button', { name: 'do-rerender' }))
    fireEvent.click(screen.getByRole('button', { name: 'do-rerender' }))
    expect(resolvers).toHaveLength(2)

    // Resolve the NEWER (B) first, then the STALE (A) last.
    await act(async () => {
      resolvers[1](templateResult('/api/mesh/1?v=new'))
    })
    await act(async () => {
      resolvers[0](templateResult('/api/mesh/1?v=stale'))
    })

    // The stale response is discarded; the newer geometry stands.
    expect(screen.getByTestId('mesh-url').textContent).toBe('/api/mesh/1?v=new')
  })
})

describe('App restore-on-load (Stage 8.5)', () => {
  it('reopens a saved design when the page loads directly on its URL', async () => {
    // S1F-003: a fresh load on `#/design/<id>` must restore the part (refresh = no lost work),
    // not drop to the landing. The restore effect calls reopenDesign with the route id.
    const api = await import('./api')
    ;(api.reopenDesign as Mock).mockResolvedValue(templateResult('/api/mesh/7'))
    window.location.hash = '#/design/abc'

    render(<App />)

    await waitFor(() => expect(api.reopenDesign).toHaveBeenCalledWith('abc'))
    // The workspace (stub) shows the restored mesh — the landing is not rendered.
    expect((await screen.findByTestId('mesh-url')).textContent).toBe('/api/mesh/7')
    expect(screen.queryByLabelText(/describe the part/i)).toBeNull()
  })

  it('does not re-save on a pure reopen until the user edits (L-2)', async () => {
    const api = await import('./api')
    ;(api.reopenDesign as Mock).mockResolvedValue({
      ...templateResult('/api/mesh/7'),
      saved_id: 'abc',
    })
    window.location.hash = '#/design/abc'

    render(<App />)
    await screen.findByTestId('mesh-url')
    // The viewport frames the restored part -> model-ready fires. The design is already saved and
    // unchanged, so NO redundant save POST should go out.
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    expect(api.saveDesign).not.toHaveBeenCalled()

    // An actual edit (re-render) clears the guard and re-saves the entry in place.
    ;(api.postRender as Mock).mockResolvedValue({ ...templateResult('/api/mesh/7?v=2'), saved_id: 'abc' })
    fireEvent.click(screen.getByRole('button', { name: 'do-rerender' }))
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    await waitFor(() => expect(api.saveDesign).toHaveBeenCalled(), { timeout: 1500 })
  })
})

describe('App auto-save lifecycle (Stage 8.5)', () => {
  it('auto-saves once on first frame and guards the duplicate-create race (TEST-001)', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock).mockResolvedValueOnce(templateResult('/api/mesh/1'))
    // Hold the first create in flight so two rapid frames overlap — the creatingRef guard must
    // allow exactly ONE create (a second would spawn a duplicate library entry).
    let resolveSave: (v: { id: string; name: string }) => void = () => {}
    ;(api.saveDesign as Mock).mockImplementation(
      () => new Promise((resolve) => { resolveSave = resolve }),
    )

    render(<App />)
    await designFrom('a box')
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    expect(api.saveDesign).toHaveBeenCalledTimes(1) // the second create is suppressed
    expect(await screen.findByText(/Saving/)).toBeTruthy() // the indicator shows the save in flight

    await act(async () => {
      resolveSave({ id: 'x', name: 'n' })
    })
    // Once persisted, the Topbar shows the resting "Saved" affordance (UX-001).
    expect(await screen.findByText(/Saved/)).toBeTruthy()
  })

  it('carries saved_id forward so a re-save updates in place, never a 2nd create (TEST-001)', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock).mockResolvedValueOnce(templateResult('/api/mesh/1'))
    ;(api.saveDesign as Mock).mockResolvedValue({ id: 'x', name: 'n' })

    render(<App />)
    await designFrom('a box')
    // First frame -> create (no saved_id).
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    await waitFor(() => expect(api.saveDesign).toHaveBeenCalledTimes(1))
    expect((api.saveDesign as Mock).mock.calls[0][3]).toBeFalsy() // create carries no saved_id
    // Second frame -> debounced re-save of the SAME entry, carrying the minted saved_id.
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    await waitFor(() => expect(api.saveDesign).toHaveBeenCalledTimes(2), { timeout: 1500 })
    expect((api.saveDesign as Mock).mock.calls[1][3]).toBe('x') // update-in-place, not a new create
  })
})
