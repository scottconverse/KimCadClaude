// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
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
})
