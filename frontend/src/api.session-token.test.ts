// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'

// #31 (KC-26): the SPA reads the per-boot session token from the shell's meta tag at module load
// and sends it (X-KimCad-Session) on state-changing requests. The token is captured in a
// module-level const, so each case sets the meta, resets modules, and re-imports api.ts fresh.

afterEach(() => {
  vi.restoreAllMocks()
  vi.resetModules()
  document.head.innerHTML = ''
})

function setMeta(content: string) {
  document.head.innerHTML = `<meta name="kimcad-session-token" content="${content}">`
}

async function freshApiWithMockedFetch() {
  vi.resetModules()
  const api = await import('./api')
  const fetchMock = vi.fn(async (_input: string, _init?: RequestInit) => ({
    ok: true,
    status: 200,
    json: async () => ({ status: 'completed', has_mesh: false }),
  }))
  vi.stubGlobal('fetch', fetchMock)
  return { api, fetchMock }
}

describe('session token header (#31 / KC-26)', () => {
  it('stamps X-KimCad-Session on a state-changing request when the shell injected a token', async () => {
    setMeta('tok-abc-123')
    const { api, fetchMock } = await freshApiWithMockedFetch()
    await api.postDesign('a box')
    const init = fetchMock.mock.calls[0][1]
    expect((init?.headers as Record<string, string> | undefined)?.['X-KimCad-Session']).toBe('tok-abc-123')
  })

  it('sends NO token header when the placeholder was never substituted (vite dev / no backend)', async () => {
    setMeta('__KIMCAD_SESSION_TOKEN__')
    const { api, fetchMock } = await freshApiWithMockedFetch()
    await api.postDesign('a box')
    const init = fetchMock.mock.calls[0][1]
    expect((init?.headers as Record<string, string> | undefined)?.['X-KimCad-Session']).toBeUndefined()
  })

  it('sends NO token header when the shell has no token meta at all', async () => {
    document.head.innerHTML = ''
    const { api, fetchMock } = await freshApiWithMockedFetch()
    await api.postDesign('a box')
    const init = fetchMock.mock.calls[0][1]
    expect((init?.headers as Record<string, string> | undefined)?.['X-KimCad-Session']).toBeUndefined()
  })
})
