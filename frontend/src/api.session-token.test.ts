// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'

// #31 (KC-26): the SPA reads the per-boot session token from the shell's meta tag at module load
// and stamps it (X-KimCad-Session) on EVERY state-changing request via apiFetch. The token is a
// module-level const, so each case sets the meta, resets modules, and re-imports api.ts fresh.

afterEach(() => {
  vi.restoreAllMocks()
  vi.resetModules()
  document.head.innerHTML = ''
})

function setMeta(content: string) {
  document.head.innerHTML = `<meta name="kimcad-session-token" content="${content}">`
}

// Robust read of the header off a recorded fetch call — works whether init.headers is a record,
// a Headers instance, an array, or undefined (apiFetch normalizes via new Headers()).
function tokenHeaderOf(fetchMock: { mock: { calls: unknown[][] } }, idx = 0): string | null {
  const init = fetchMock.mock.calls[idx]?.[1] as RequestInit | undefined
  return new Headers(init?.headers).get('X-KimCad-Session')
}

function mockOkFetch() {
  const fetchMock = vi.fn(async (_input: string, _init?: RequestInit) => ({
    ok: true,
    status: 200,
    json: async () => ({ status: 'completed', has_mesh: false, saved: true, id: 'x', missing: [] }),
  }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('session token header (#31 / KC-26)', () => {
  it('stamps X-KimCad-Session when the shell injected a token', async () => {
    setMeta('tok-abc-123')
    vi.resetModules()
    const api = await import('./api')
    const fetchMock = mockOkFetch()
    await api.postDesign('a box')
    expect(tokenHeaderOf(fetchMock)).toBe('tok-abc-123')
  })

  it('sends NO header for the un-substituted dev placeholder', async () => {
    setMeta('__KIMCAD_SESSION_TOKEN__')
    vi.resetModules()
    const api = await import('./api')
    const fetchMock = mockOkFetch()
    await api.postDesign('a box')
    expect(tokenHeaderOf(fetchMock)).toBeNull()
  })

  it('sends NO header when the shell has no token meta', async () => {
    document.head.innerHTML = ''
    vi.resetModules()
    const api = await import('./api')
    const fetchMock = mockOkFetch()
    await api.postDesign('a box')
    expect(tokenHeaderOf(fetchMock)).toBeNull()
  })

  it('stamps the header across the different POST shapes (postJson, raw-body upload, no-headers)', async () => {
    setMeta('tok-shapes')
    vi.resetModules()
    const api = await import('./api')
    const fetchMock = mockOkFetch()
    // postJson-based (postSettings), the no-headers path (startModelPull), and a raw-File upload
    // (importDesign) — each a distinct apiFetch call shape that must still carry the token.
    await api.postSettings({ default_printer: 'bambu_p2s' }).catch(() => {})
    await api.startModelPull().catch(() => {})
    await api.importDesign(new File([new Uint8Array([1, 2, 3])], 'd.kimcad')).catch(() => {})
    expect(tokenHeaderOf(fetchMock, 0)).toBe('tok-shapes') // postSettings (postJson)
    expect(tokenHeaderOf(fetchMock, 1)).toBe('tok-shapes') // startModelPull (no headers object)
    expect(tokenHeaderOf(fetchMock, 2)).toBe('tok-shapes') // importDesign (raw body)
  })

  it('a 403 reason:"session" throws SessionExpiredError AND fires the app recovery handler', async () => {
    setMeta('stale-tok')
    vi.resetModules()
    const api = await import('./api')
    let recovered = false
    api.setSessionExpiredHandler(() => {
      recovered = true
    })
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ error: 'Missing or invalid session token. Reload TinkerQuarry.', reason: 'session' }),
    })))
    await expect(api.postDesign('a box')).rejects.toBeInstanceOf(api.SessionExpiredError)
    expect(recovered).toBe(true)
    expect(api.isSessionExpired(new api.SessionExpiredError('x'))).toBe(true)
    api.setSessionExpiredHandler(null)
  })

  it('a plain 403 (no session reason) stays an ordinary error, not SessionExpiredError', async () => {
    setMeta('tok')
    vi.resetModules()
    const api = await import('./api')
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ error: 'Forbidden.' }),
    })))
    await expect(api.postDesign('a box')).rejects.toThrow('Forbidden.')
    await expect(api.postDesign('a box')).rejects.not.toBeInstanceOf(api.SessionExpiredError)
  })
})
