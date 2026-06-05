// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi, type Mock } from 'vitest'
import type { CompareMessage, DesignResponse, DesignVersion, Message } from './api'
import App from './App'

// Mock the API so we control timing without a server.
vi.mock('./api', () => ({
  postDesign: vi.fn(),
  postRender: vi.fn(),
  reopenDesign: vi.fn(),
  saveDesign: vi.fn().mockResolvedValue({ id: 'x', name: 'n' }),
  designIdFromMeshUrl: () => 1,
  // Real-ish helper so the cancel path classifies an AbortError correctly.
  isAbortError: (e: unknown) => (e as { name?: string })?.name === 'AbortError',
}))

// Replace the (three.js) Workspace so the test doesn't pull in WebGL.
vi.mock('./components/Workspace', () => ({
  default: ({
    messages,
    compareCard,
    versions,
    versionIdx,
    rerendering,
    busy,
    busyElapsed,
    onCancelDesign,
    onRerender,
    onRefine,
    onSwitchVersion,
    onCompare,
    onModelReady,
    result,
  }: {
    messages: Message[]
    compareCard: CompareMessage | null
    versions: DesignVersion[]
    versionIdx: number
    rerendering: boolean
    busy: boolean
    busyElapsed: number
    onCancelDesign: () => void
    onRerender: (values: Record<string, number>) => void
    onRefine: (text: string) => void
    onSwitchVersion: (idx: number) => void
    onCompare: (a: number, b: number) => void
    onModelReady: (capture: () => string | null) => void
    result: DesignResponse | null
  }) => (
    <div>
      <span data-testid="rerendering">{String(rerendering)}</span>
      <span data-testid="busy">{String(busy)}</span>
      <span data-testid="busy-elapsed">{busyElapsed}</span>
      <span data-testid="mesh-url">{result?.mesh_url ?? ''}</span>
      <span data-testid="msg-count">{messages.length}</span>
      <span data-testid="version-count">{versions.length}</span>
      <span data-testid="version-idx">{versionIdx}</span>
      <span data-testid="compare-card">{compareCard ? 'yes' : 'no'}</span>
      <button type="button" onClick={() => onRerender({ width: 1 })}>do-rerender</button>
      <button type="button" onClick={() => onModelReady(() => 'data:image/png;base64,AA')}>frame-model</button>
      <button type="button" onClick={() => onRefine('make it bigger')}>do-refine</button>
      <button type="button" onClick={() => onSwitchVersion(0)}>switch-v1</button>
      <button type="button" onClick={() => onCompare(0, 1)}>do-compare</button>
      <button type="button" onClick={onCancelDesign}>cancel-design</button>
    </div>
  ),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  window.location.hash = ''
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
  return screen.findByTestId('rerendering')
}

describe('App live-slider lifecycle', () => {
  it('clears the re-render flag when a new design abandons an in-flight re-render', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock)
      .mockResolvedValueOnce(templateResult('/api/mesh/1'))
      .mockResolvedValueOnce(templateResult('/api/mesh/1?v=9'))
    ;(api.postRender as Mock).mockReturnValue(new Promise<DesignResponse>(() => {}))

    render(<App />)
    const flag = await designFrom('a box')
    expect(flag.textContent).toBe('false')

    fireEvent.click(screen.getByRole('button', { name: 'do-rerender' }))
    expect(screen.getByTestId('rerendering').textContent).toBe('true')

    fireEvent.click(screen.getByRole('button', { name: /new design/i }))
    const flag2 = await designFrom('a different box')
    expect(flag2.textContent).toBe('false')
  })

  it('discards a stale (out-of-order) re-render response so the newer one wins', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock).mockResolvedValueOnce(templateResult('/api/mesh/1'))
    const resolvers: Array<(v: DesignResponse) => void> = []
    ;(api.postRender as Mock).mockImplementation(
      () => new Promise<DesignResponse>((resolve) => resolvers.push(resolve)),
    )

    render(<App />)
    await designFrom('a box')

    fireEvent.click(screen.getByRole('button', { name: 'do-rerender' }))
    fireEvent.click(screen.getByRole('button', { name: 'do-rerender' }))
    expect(resolvers).toHaveLength(2)

    await act(async () => { resolvers[1](templateResult('/api/mesh/1?v=new')) })
    await act(async () => { resolvers[0](templateResult('/api/mesh/1?v=stale')) })

    expect(screen.getByTestId('mesh-url').textContent).toBe('/api/mesh/1?v=new')
  })
})

describe('App restore-on-load (Stage 8.5)', () => {
  it('reopens a saved design when the page loads directly on its URL', async () => {
    const api = await import('./api')
    ;(api.reopenDesign as Mock).mockResolvedValue(templateResult('/api/mesh/7'))
    window.location.hash = '#/design/abc'

    render(<App />)

    await waitFor(() => expect(api.reopenDesign).toHaveBeenCalledWith('abc'))
    expect((await screen.findByTestId('mesh-url')).textContent).toBe('/api/mesh/7')
    expect(screen.queryByLabelText(/describe the part/i)).toBeNull()
  })

  it('does not re-save on a pure reopen until the user edits (L-2)', async () => {
    const api = await import('./api')
    ;(api.reopenDesign as Mock).mockResolvedValue({ ...templateResult('/api/mesh/7'), saved_id: 'abc' })
    window.location.hash = '#/design/abc'

    render(<App />)
    await screen.findByTestId('mesh-url')
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    expect(api.saveDesign).not.toHaveBeenCalled()

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
    let resolveSave: (v: { id: string; name: string }) => void = () => {}
    ;(api.saveDesign as Mock).mockImplementation(
      () => new Promise((resolve) => { resolveSave = resolve }),
    )

    render(<App />)
    await designFrom('a box')
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    expect(api.saveDesign).toHaveBeenCalledTimes(1)
    expect(await screen.findByText(/Saving/)).toBeTruthy()

    await act(async () => { resolveSave({ id: 'x', name: 'n' }) })
    expect(await screen.findByText(/Saved/)).toBeTruthy()
  })

  it('carries saved_id forward so a re-save updates in place, never a 2nd create (TEST-001)', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock).mockResolvedValueOnce(templateResult('/api/mesh/1'))
    ;(api.saveDesign as Mock).mockResolvedValue({ id: 'x', name: 'n' })

    render(<App />)
    await designFrom('a box')
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    await waitFor(() => expect(api.saveDesign).toHaveBeenCalledTimes(1))
    expect((api.saveDesign as Mock).mock.calls[0][3]).toBeFalsy()
    fireEvent.click(screen.getByRole('button', { name: 'frame-model' }))
    await waitFor(() => expect(api.saveDesign).toHaveBeenCalledTimes(2), { timeout: 1500 })
    expect((api.saveDesign as Mock).mock.calls[1][3]).toBe('x')
  })
})

describe('App refinement thread (Stage 8.5 Slice 2)', () => {
  it('pushes a version on each successful design', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock)
      .mockResolvedValueOnce(templateResult('/api/mesh/1'))
      .mockResolvedValueOnce(templateResult('/api/mesh/2'))

    render(<App />)
    await designFrom('a box')
    expect(screen.getByTestId('version-count').textContent).toBe('1')
    expect(screen.getByTestId('version-idx').textContent).toBe('0')

    fireEvent.click(screen.getByRole('button', { name: 'do-refine' }))
    await waitFor(() => expect(screen.getByTestId('version-count').textContent).toBe('2'))
    expect(screen.getByTestId('version-idx').textContent).toBe('1')
  })

  it('switch-version restores prior messages + result', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock)
      .mockResolvedValueOnce(templateResult('/api/mesh/1'))
      .mockResolvedValueOnce(templateResult('/api/mesh/2'))

    render(<App />)
    await designFrom('a box')
    fireEvent.click(screen.getByRole('button', { name: 'do-refine' }))
    await waitFor(() => expect(screen.getByTestId('version-count').textContent).toBe('2'))
    expect(screen.getByTestId('mesh-url').textContent).toBe('/api/mesh/2')

    // Switch back to v1
    fireEvent.click(screen.getByRole('button', { name: 'switch-v1' }))
    expect(screen.getByTestId('mesh-url').textContent).toBe('/api/mesh/1')
    expect(screen.getByTestId('version-idx').textContent).toBe('0')
    // Message count drops back to v1's 2 messages
    expect(screen.getByTestId('msg-count').textContent).toBe('2')
  })

  it('builds a conversation thread across multiple turns', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock)
      .mockResolvedValueOnce(templateResult('/api/mesh/1'))
      .mockResolvedValueOnce(templateResult('/api/mesh/2'))

    render(<App />)
    await designFrom('a box')
    // After first design: user + assistant = 2 messages
    expect(screen.getByTestId('msg-count').textContent).toBe('2')

    // Fire a refine turn
    fireEvent.click(screen.getByRole('button', { name: 'do-refine' }))
    await waitFor(() => expect(api.postDesign).toHaveBeenCalledTimes(2))
    // After refine: user + assistant + user + assistant = 4 messages
    expect(screen.getByTestId('msg-count').textContent).toBe('4')
  })

  it('threads prior history into postDesign on a refine turn', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock)
      .mockResolvedValueOnce(templateResult('/api/mesh/1'))
      .mockResolvedValueOnce(templateResult('/api/mesh/2'))

    render(<App />)
    await designFrom('a box')

    fireEvent.click(screen.getByRole('button', { name: 'do-refine' }))
    await waitFor(() => expect(api.postDesign).toHaveBeenCalledTimes(2))

    const secondCall = (api.postDesign as Mock).mock.calls[1]
    // Second call carries history from the first turn
    expect(secondCall[1]).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ role: 'user', content: 'a box' }),
        expect.objectContaining({ role: 'assistant' }),
      ])
    )
  })

  it('refine after switch-back branches: drops forward versions', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock)
      .mockResolvedValueOnce(templateResult('/api/mesh/1'))  // v1
      .mockResolvedValueOnce(templateResult('/api/mesh/2'))  // v2
      .mockResolvedValueOnce(templateResult('/api/mesh/3'))  // v3 (branched from v1)

    render(<App />)
    await designFrom('a box')
    // Refine -> v2
    fireEvent.click(screen.getByRole('button', { name: 'do-refine' }))
    await waitFor(() => expect(screen.getByTestId('version-count').textContent).toBe('2'))
    // Step back to v1
    fireEvent.click(screen.getByRole('button', { name: 'switch-v1' }))
    expect(screen.getByTestId('version-idx').textContent).toBe('0')
    // Refine from v1 -> should create v2' and drop old v2
    fireEvent.click(screen.getByRole('button', { name: 'do-refine' }))
    await waitFor(() => expect(api.postDesign).toHaveBeenCalledTimes(3))
    // Still 2 versions (v1 + new v2), not 3
    expect(screen.getByTestId('version-count').textContent).toBe('2')
  })

  it('compare sets a compareCard with both versions', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock)
      .mockResolvedValueOnce(templateResult('/api/mesh/1'))
      .mockResolvedValueOnce(templateResult('/api/mesh/2'))

    render(<App />)
    await designFrom('a box')
    fireEvent.click(screen.getByRole('button', { name: 'do-refine' }))
    await waitFor(() => expect(screen.getByTestId('version-count').textContent).toBe('2'))

    expect(screen.getByTestId('compare-card').textContent).toBe('no')
    fireEvent.click(screen.getByRole('button', { name: 'do-compare' }))
    expect(screen.getByTestId('compare-card').textContent).toBe('yes')
  })

  it('resets the thread on new design', async () => {
    const api = await import('./api')
    ;(api.postDesign as Mock)
      .mockResolvedValue(templateResult('/api/mesh/1'))

    render(<App />)
    await designFrom('a box')
    expect(screen.getByTestId('msg-count').textContent).toBe('2')

    fireEvent.click(screen.getByRole('button', { name: /new design/i }))
    // Landing shown, no workspace thread
    expect(screen.queryByTestId('msg-count')).toBeNull()
  })
})

describe('App cancel / escape the "Designing…" screen (Stage 8.5)', () => {
  it('cancel aborts the in-flight design and returns to the prompt (never stuck)', async () => {
    const api = await import('./api')
    // postDesign honors the AbortSignal (4th arg) — it rejects with an AbortError when cancelled,
    // exactly like a real aborted fetch. Otherwise it stays pending (the model is "working").
    ;(api.postDesign as Mock).mockImplementation(
      (_p: string, _h: unknown, _e: boolean, signal?: AbortSignal) =>
        new Promise<DesignResponse>((_resolve, reject) => {
          signal?.addEventListener('abort', () =>
            reject(Object.assign(new Error('aborted'), { name: 'AbortError' })),
          )
        }),
    )

    render(<App />)
    fireEvent.change(screen.getByLabelText(/describe the part/i), { target: { value: 'a frame stand' } })
    fireEvent.click(screen.getByRole('button', { name: /design it/i }))

    // We're in the workspace, busy, with the elapsed counter wired.
    expect((await screen.findByTestId('busy')).textContent).toBe('true')
    expect(screen.getByTestId('busy-elapsed').textContent).toMatch(/^\d+$/)

    // Hit Cancel — the request aborts and we drop back to the landing prompt, no longer stuck.
    fireEvent.click(screen.getByRole('button', { name: 'cancel-design' }))
    await waitFor(() => expect(screen.getByLabelText(/describe the part/i)).toBeTruthy())
    expect(screen.queryByTestId('busy')).toBeNull()
  })

  it('drops a superseded design’s late result (escape via New Design must not be polluted)', async () => {
    const api = await import('./api')
    let resolveA: (v: DesignResponse) => void = () => {}
    ;(api.postDesign as Mock)
      .mockImplementationOnce(() => new Promise<DesignResponse>((res) => { resolveA = res })) // A hangs
      .mockResolvedValueOnce(templateResult('/api/mesh/2')) // B completes

    render(<App />)
    fireEvent.change(screen.getByLabelText(/describe the part/i), { target: { value: 'design A' } })
    fireEvent.click(screen.getByRole('button', { name: /design it/i }))
    expect((await screen.findByTestId('busy')).textContent).toBe('true')

    // Escape via New Design, then run B to completion.
    fireEvent.click(screen.getByRole('button', { name: /new design/i }))
    fireEvent.change(screen.getByLabelText(/describe the part/i), { target: { value: 'design B' } })
    fireEvent.click(screen.getByRole('button', { name: /design it/i }))
    await screen.findByTestId('mesh-url')
    expect(screen.getByTestId('mesh-url').textContent).toBe('/api/mesh/2')

    // A resolves LATE — the seq guard must drop it so B's session isn't clobbered.
    await act(async () => { resolveA(templateResult('/api/mesh/1')) })
    expect(screen.getByTestId('mesh-url').textContent).toBe('/api/mesh/2')
    expect(screen.getByTestId('version-count').textContent).toBe('1') // no stale extra version
  })
})
