// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DesignResponse } from '../api'
import ExportPanel from './ExportPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function stubFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (String(url).includes('/api/options')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            printers: [
              { key: 'p', name: 'P', sliceable: true, materials: ['pla'], generic_materials: [] },
            ],
            materials: [{ key: 'pla', name: 'PLA' }],
            default_printer: 'p',
            default_material: 'pla',
          }),
        }
      }
      return { ok: true, status: 200, json: async () => ({ connectors: [], default: null }) }
    }),
  )
}

const base = (gate: string): DesignResponse => ({
  status: gate === 'fail' ? 'gate_failed' : 'completed',
  has_mesh: true,
  mesh_url: '/api/mesh/1',
  plan: { object_type: 'box', summary: 'a box', target_bbox_mm: [80, 60, 40] },
  report: { gate_status: gate, headline: '', dims: [], findings: [] },
})

describe('ExportPanel gate-awareness', () => {
  it('refuses to slice a gate-FAILED part (no slice control) but still offers the model download', () => {
    stubFetch()
    render(<ExportPanel result={base('fail')} />)
    expect(screen.queryByRole('button', { name: /slice & prepare/i })).toBeNull()
    expect(screen.getByText(/can.t be sliced/i)).toBeTruthy()
    expect(screen.getByText(/download 3d model/i)).toBeTruthy()
  })

  it('offers the slice control for a gate-passing part', () => {
    stubFetch()
    render(<ExportPanel result={base('pass')} />)
    expect(screen.getByRole('button', { name: /slice & prepare/i })).toBeTruthy()
  })

  it('shows the empty state before a part exists', () => {
    stubFetch()
    render(<ExportPanel result={null} />)
    expect(screen.getByText(/once a part is designed/i)).toBeTruthy()
  })

  it('lets the user cancel an in-flight slice and return to the button — never stuck (escape)', async () => {
    // options resolve; the slice hangs until its AbortSignal fires (mirrors a slow OrcaSlicer run).
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (String(url).includes('/api/options')) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              printers: [{ key: 'p', name: 'P', sliceable: true, materials: ['pla'], generic_materials: [] }],
              materials: [{ key: 'pla', name: 'PLA' }],
              default_printer: 'p',
              default_material: 'pla',
            }),
          }
        }
        if (String(url).includes('/api/slice/')) {
          return await new Promise((_res, rej) => {
            init?.signal?.addEventListener('abort', () =>
              rej(Object.assign(new Error('aborted'), { name: 'AbortError' })),
            )
          })
        }
        return { ok: true, status: 200, json: async () => ({ connectors: [], default: null }) }
      }),
    )
    render(<ExportPanel result={base('pass')} />)
    const sliceBtn = await screen.findByRole('button', { name: /slice & prepare/i })
    await waitFor(() => expect((sliceBtn as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(sliceBtn)
    // Slicing… + a Cancel appears.
    expect(await screen.findByRole('button', { name: /^Cancel$/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Slicing/i })).toBeTruthy()
    // Cancel aborts and returns to the slice button, with NO error surfaced (a cancel isn't a
    // failure — this catches an isAbortError-miss that would leak the raw "aborted" message).
    fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /slice & prepare/i })).toBeTruthy())
    expect(screen.queryByText(/slicing failed/i)).toBeNull()
    expect(document.querySelector('.kc-export-error')).toBeNull()
    expect(screen.queryByText(/aborted/i)).toBeNull()
  })
})
