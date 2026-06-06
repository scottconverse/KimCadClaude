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

  it('surfaces the export formats with the STEP/BREP note', () => {
    stubFetch()
    render(<ExportPanel result={base('pass')} />)
    expect(screen.getByText(/download 3d model \(\.stl\)/i)).toBeTruthy()
    expect(screen.getByText(/STEP and BREP/i)).toBeTruthy()
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

// Slice 10 — once a part is sliced, show the estimate broken out into labeled stats, the print
// file with a name + copy-link affordance, and the "design → print" framing.
function stubFetchWithSlice(slice: Record<string, unknown>) {
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
      if (String(url).includes('/api/slice/')) {
        return { ok: true, status: 200, json: async () => slice }
      }
      return { ok: true, status: 200, json: async () => ({ connectors: [], default: null }) }
    }),
  )
}

async function runSlice() {
  const btn = await screen.findByRole('button', { name: /slice & prepare/i })
  await waitFor(() => expect((btn as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(btn)
}

describe('ExportPanel print summary (Slice 10)', () => {
  const SLICED = {
    sliced: true,
    printer: 'Bambu P2S',
    material: 'PLA',
    estimate: '~1h 12m, 84 layers, 9.3 g filament',
    estimate_detail: {
      time: '1h 12m',
      layers: 84,
      filament_mm: 3120,
      filament_cm3: 7.5,
      filament_g: 9.3,
    },
    gcode_url: '/api/gcode/1',
    gcode_filename: 'part_bambu_p2s_pla.gcode.3mf',
  }

  it('breaks the estimate into labeled stats (time, layers, filament length + weight)', async () => {
    stubFetchWithSlice(SLICED)
    render(<ExportPanel result={base('pass')} />)
    await runSlice()
    // labels
    expect(await screen.findByText('Print time')).toBeTruthy()
    expect(screen.getByText('Layers')).toBeTruthy()
    expect(screen.getByText('Filament')).toBeTruthy()
    expect(screen.getByText('Weight')).toBeTruthy()
    // values (length rolls up to metres past 1 m; weight in grams)
    expect(screen.getByText('~1h 12m')).toBeTruthy()
    expect(screen.getByText('84')).toBeTruthy()
    expect(screen.getByText('3.12 m')).toBeTruthy()
    expect(screen.getByText('9.3 g')).toBeTruthy()
    // the print file is named, and the part→print framing is present
    expect(screen.getByText('part_bambu_p2s_pla.gcode.3mf')).toBeTruthy()
    expect(screen.getByText(/here.s your print/i)).toBeTruthy()
  })

  it('copies the absolute print-file link to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    stubFetchWithSlice(SLICED)
    render(<ExportPanel result={base('pass')} />)
    await runSlice()
    const copyBtn = await screen.findByRole('button', { name: /copy link/i })
    fireEvent.click(copyBtn)
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1))
    expect(writeText.mock.calls[0][0]).toMatch(/\/api\/gcode\/1$/)
    // absolute, not the bare relative path
    expect(writeText.mock.calls[0][0]).toMatch(/^https?:\/\//)
    expect(await screen.findByRole('button', { name: /copied/i })).toBeTruthy()
  })

  it('labels the weight as an estimate when KimCad derived it from volume', async () => {
    stubFetchWithSlice({ ...SLICED, estimate_detail: { ...SLICED.estimate_detail, filament_g_estimated: true } })
    render(<ExportPanel result={base('pass')} />)
    await runSlice()
    expect(await screen.findByText('9.3 g')).toBeTruthy()
    expect(screen.getByText(/weight is estimated/i)).toBeTruthy()
  })

  it('never shows the estimate footnote without a weight beside it (no orphan caption)', async () => {
    // flag set but no renderable grams (degenerate slice): the caption must not appear alone.
    stubFetchWithSlice({
      ...SLICED,
      estimate_detail: {
        time: '5m',
        layers: 10,
        filament_mm: 200,
        filament_cm3: 0,
        filament_g: null,
        filament_g_estimated: true,
      },
    })
    render(<ExportPanel result={base('pass')} />)
    await runSlice()
    expect(await screen.findByText('Print time')).toBeTruthy()
    expect(screen.queryByText('Weight')).toBeNull()
    expect(screen.queryByText(/weight is estimated/i)).toBeNull()
  })

  it('does not call the weight an estimate when the slicer computed it', async () => {
    stubFetchWithSlice(SLICED) // filament_g_estimated falsy
    render(<ExportPanel result={base('pass')} />)
    await runSlice()
    expect(await screen.findByText('9.3 g')).toBeTruthy()
    expect(screen.queryByText(/weight is estimated/i)).toBeNull()
  })

  it('falls back to the plain summary when no structured detail is present', async () => {
    stubFetchWithSlice({
      sliced: true,
      printer: 'P',
      material: 'PLA',
      estimate: '~14m 45s',
      estimate_detail: null,
      gcode_url: '/api/gcode/1',
      gcode_filename: 'part.gcode.3mf',
    })
    render(<ExportPanel result={base('pass')} />)
    await runSlice()
    expect(await screen.findByText('~14m 45s')).toBeTruthy()
    // no fabricated stat labels when the slicer reported nothing structured
    expect(screen.queryByText('Layers')).toBeNull()
  })
})
