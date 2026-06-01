import { afterEach, describe, expect, it, vi } from 'vitest'
import { postDesign } from './api'

afterEach(() => {
  vi.restoreAllMocks()
})

function mockFetch(impl: () => Promise<unknown>) {
  vi.stubGlobal('fetch', vi.fn(impl))
}

describe('postDesign', () => {
  it('returns the parsed body on a 200', async () => {
    mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ status: 'completed', has_mesh: false }),
    }))
    const result = await postDesign('a box')
    expect(result.status).toBe('completed')
    expect(result.has_mesh).toBe(false)
  })

  it('throws the backend error message on a non-2xx', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 400,
      json: async () => ({ error: 'Please describe the part you want.' }),
    }))
    await expect(postDesign('')).rejects.toThrow('Please describe the part you want.')
  })

  it('throws a readable error when the body is not JSON', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error('not json')
      },
    }))
    await expect(postDesign('x')).rejects.toThrow(/unreadable/i)
  })
})
