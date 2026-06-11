// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { openExternal } from './openExternal'

afterEach(() => {
  delete (window as unknown as Record<string, unknown>).pywebview
  vi.restoreAllMocks()
})

describe('openExternal (Slice 11.6)', () => {
  it('uses the shell bridge when the app runs inside the WebView2 window', () => {
    const bridged: string[] = []
    ;(window as unknown as Record<string, unknown>).pywebview = {
      api: { open_external: (u: string) => bridged.push(u) },
    }
    const opened = vi.spyOn(window, 'open').mockReturnValue(null)
    openExternal('https://ollama.com/download')
    expect(bridged).toEqual(['https://ollama.com/download'])
    expect(opened).not.toHaveBeenCalled() // never navigate the APP window away
  })

  it('falls back to a new browser tab outside the shell (kimcad web)', () => {
    const opened = vi.spyOn(window, 'open').mockReturnValue(null)
    openExternal('https://ollama.com/download')
    expect(opened).toHaveBeenCalledWith('https://ollama.com/download', '_blank', 'noopener')
  })
})
