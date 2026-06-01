// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DesignResponse } from '../api'
import RightPanel from './RightPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// RightPanel embeds ExportPanel, which fetches /api/options + /api/connectors on mount — stub
// fetch so those effects resolve quietly (the assertions below are on the synchronous render).
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

const passResult: DesignResponse = {
  status: 'completed',
  has_mesh: true,
  mesh_url: '/api/mesh/1',
  plan: { object_type: 'box', summary: 'a box', target_bbox_mm: [80, 60, 40] },
  report: {
    gate_status: 'pass',
    headline: 'Dimensions match the request',
    dims: [{ axis: 'X', target: 80, actual: 80, ok: true }],
    findings: [{ level: 'pass', code: 'dim', message: 'Dimensions match' }],
  },
}

describe('RightPanel', () => {
  it('renders the printability verdict, the size, and findings from the result', () => {
    stubFetch()
    render(<RightPanel result={passResult} />)
    expect(screen.getByText('Ready to print')).toBeTruthy()
    expect(screen.getByText('Dimensions match')).toBeTruthy()
    expect(screen.getByText(/80 × 60 × 40 mm/)).toBeTruthy()
  })

  it('shows placeholders when there is no result yet', () => {
    stubFetch()
    render(<RightPanel result={null} />)
    expect(screen.getByText(/parameters will appear here/i)).toBeTruthy()
    expect(screen.getByText(/printability check .* appears here/i)).toBeTruthy()
  })
})
