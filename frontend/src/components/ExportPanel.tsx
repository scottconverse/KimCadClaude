import { useEffect, useMemo, useRef, useState } from 'react'
import {
  designIdFromMeshUrl,
  getOptions,
  isAbortError,
  postSlice,
  type DesignResponse,
  type OptionsResponse,
  type SliceResponse,
} from '../api'
import { buildEstimateRows } from '../printEstimate'
import ConnectorStatus from './ConnectorStatus'
import SendPanel from './SendPanel'

// Export & print (Stage 4, Slice 5): pick a printer + material, slice the already-validated,
// oriented mesh on confirmation, and download the proven G-code (or the model). Gate-aware — a
// part that failed the printability gate can't be sliced (the server refuses too), but the model
// stays downloadable to inspect. Stage 10 adds the direct-print SendPanel under a finished slice.
export default function ExportPanel({ result }: { result: DesignResponse | null }) {
  const [options, setOptions] = useState<OptionsResponse | null>(null)
  const [printer, setPrinter] = useState('')
  const [material, setMaterial] = useState('')
  const [materialSlots, setMaterialSlots] = useState<string[]>([])
  const [slicing, setSlicing] = useState(false)
  const [slice, setSlice] = useState<SliceResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Slicing (OrcaSlicer) can take a while — let the user cancel and escape the "Slicing…" wait.
  const sliceAbortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    let cancelled = false
    getOptions()
      .then((o) => {
        if (cancelled) return
        setOptions(o)
        setPrinter(o.default_printer || o.printers[0]?.key || '')
      })
      .catch(() => {
        /* options unavailable — the card still offers a model download below */
      })
    return () => {
      cancelled = true
    }
  }, [])

  const selectedPrinter = options?.printers.find((p) => p.key === printer) ?? null

  const materials = useMemo(() => {
    if (!options || !selectedPrinter) return []
    return selectedPrinter.materials
      .map((key) => options.materials.find((m) => m.key === key))
      .filter((m): m is NonNullable<typeof m> => m != null)
  }, [options, selectedPrinter])

  // The EFFECTIVE material is always valid for the chosen printer (each printer offers only the
  // materials it has a verified profile for) — derived, so the controlled <select> never lags a
  // printer change with a stale/blank value (which would also log a React warning). `material`
  // holds the user's explicit pick; this falls back to the configured default or the first.
  const selectedMaterial = useMemo(() => {
    if (materials.length === 0) return ''
    if (materials.some((m) => m.key === material)) return material
    const fallback = options?.default_material
    if (fallback && materials.some((m) => m.key === fallback)) return fallback
    return materials[0].key
  }, [materials, material, options])

  // Reset per-toolhead slots when printer or effective material changes.
  useEffect(() => {
    const count = selectedPrinter?.toolhead_count ?? 1
    if (count > 1) {
      setMaterialSlots(Array(count).fill(selectedMaterial || materials[0]?.key || ''))
    } else {
      setMaterialSlots([])
    }
  }, [printer, selectedMaterial]) // eslint-disable-line react-hooks/exhaustive-deps

  // A new design clears the previous slice result.
  useEffect(() => {
    setSlice(null)
    setError(null)
  }, [result?.mesh_url])

  // UX-004: for a multi-head printer, the post-slice summary surfaces the per-extruder material
  // assignments (KEY → display name from the in-scope `materials` list). Empty for a single head —
  // that summary keeps showing the one primary material.
  const isMultiHead = (selectedPrinter?.toolhead_count ?? 1) > 1
  const slotMaterialNames = useMemo(() => {
    if (!isMultiHead) return []
    return materialSlots.map((key) => materials.find((m) => m.key === key)?.name ?? key)
  }, [isMultiHead, materialSlots, materials])

  const designId = designIdFromMeshUrl(result?.mesh_url)
  const gateFailed = result?.report?.gate_status === 'fail'
  const canSlice =
    designId != null &&
    !gateFailed &&
    selectedPrinter?.sliceable === true &&
    selectedMaterial !== '' &&
    !slicing

  async function handleSlice() {
    if (designId == null || !canSlice) return
    sliceAbortRef.current?.abort() // supersede any prior in-flight slice
    const controller = new AbortController()
    sliceAbortRef.current = controller
    setSlicing(true)
    setError(null)
    setSlice(null)
    try {
      const slots = (selectedPrinter?.toolhead_count ?? 1) > 1 ? materialSlots : undefined
      setSlice(await postSlice(designId, printer, selectedMaterial, controller.signal, slots))
    } catch (err) {
      if (!isAbortError(err)) setError(err instanceof Error ? err.message : 'Slicing failed.')
      // a cancel just returns to the button — no error
    } finally {
      if (sliceAbortRef.current === controller) sliceAbortRef.current = null
      setSlicing(false)
    }
  }

  function cancelSlice() {
    sliceAbortRef.current?.abort()
  }

  // Abort any in-flight slice on unmount (e.g. navigating away) so it doesn't linger.
  useEffect(() => () => sliceAbortRef.current?.abort(), [])

  if (!result?.has_mesh) {
    return (
      <section className="kc-card">
        <h2 className="kc-card-title">Export &amp; print</h2>
        <p className="kc-muted-note">
          Once a part is designed you can pick a printer, slice it, and download the file.
        </p>
      </section>
    )
  }

  return (
    <section className="kc-card" id="kc-export-card">
      <h2 className="kc-card-title">Export &amp; print</h2>
      {/* UX-1007 (stage-10 gate): a green "Ready" connection pill directly above "this
          part can't be sliced" reads as a contradiction — readiness of the printer is
          irrelevant to a part that can never reach it, so the pill sits out gate-failed. */}
      {!gateFailed && <ConnectorStatus />}

      {gateFailed ? (
        <p className="kc-muted-note">
          This part didn&rsquo;t pass the printability check, so it can&rsquo;t be sliced. You can
          still download the model to inspect it.
        </p>
      ) : (
        <>
          <label className="kc-field">
            <span>Printer</span>
            <select value={printer} onChange={(e) => setPrinter(e.target.value)}>
              {options?.printers.map((p) => (
                <option key={p.key} value={p.key} disabled={!p.sliceable}>
                  {p.name}
                  {p.sliceable ? '' : ' (no slicer profile)'}
                </option>
              ))}
            </select>
          </label>

          {(selectedPrinter?.toolhead_count ?? 1) > 1 ? (
            <>
              {/* UX-002: name each slot by its physical extruder and say what assigning one does,
                  so "Extruder 2: TPU" reads plainly instead of the slicer-jargon "T2 Material". */}
              <p className="kc-muted-note">
                Assign a filament to each extruder — the slicer tunes temperature and retraction per
                slot.
              </p>
              {/* UX-003: a wrapping grid keeps many extruders compact and the Slice button visible. */}
              <div className="kc-material-slots">
                {materialSlots.map((slot, i) => (
                  <label key={i} htmlFor={`kc-slot-${i}`} className="kc-field">
                    <span id={`kc-slot-label-${i}`}>Extruder {i + 1}</span>
                    <select
                      id={`kc-slot-${i}`}
                      aria-labelledby={`kc-slot-label-${i}`}
                      value={slot}
                      onChange={(e) => {
                        const next = [...materialSlots]
                        next[i] = e.target.value
                        setMaterialSlots(next)
                      }}
                    >
                      {materials.map((m) => (
                        <option key={m.key} value={m.key}>
                          {m.name}
                          {selectedPrinter?.generic_materials.includes(m.key)
                            ? ' (generic profile)'
                            : ''}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
            </>
          ) : (
            <label className="kc-field">
              <span>Material</span>
              <select value={selectedMaterial} onChange={(e) => setMaterial(e.target.value)}>
                {materials.map((m) => (
                  <option key={m.key} value={m.key}>
                    {m.name}
                    {selectedPrinter?.generic_materials.includes(m.key) ? ' (generic profile)' : ''}
                  </option>
                ))}
              </select>
            </label>
          )}

          <div className="kc-slice-actions">
            <button
              type="button"
              className="kc-btn kc-btn-accent kc-slice-btn"
              onClick={handleSlice}
              disabled={!canSlice}
            >
              {slicing ? 'Slicing…' : 'Slice & prepare file'}
            </button>
            {slicing && (
              <button type="button" className="kc-btn kc-btn-ghost" onClick={cancelSlice}>
                Cancel
              </button>
            )}
          </div>
          {/* UX-015: say WHY the Slice button is disabled when the chosen printer has no profile. */}
          {selectedPrinter != null && selectedPrinter.sliceable !== true && (
            <p className="kc-muted-note">
              This printer doesn&rsquo;t have a slicer profile yet — pick another printer above to
              prepare a print file.
            </p>
          )}
          {/* UX-003 (2026-06-09 audit): a warn-gate part slices on purpose, but the enabled
              button must not read as a clean bill — echo the caution right next to the action. */}
          {result.report?.gate_status === 'warn' && (
            <p className="kc-muted-note kc-slice-caution">
              Slicing with cautions — review the risks in the Readiness card first.
            </p>
          )}

          {error !== null && <p className="kc-muted-note kc-export-error">{error}</p>}
          {slice && !slice.sliced && (
            <p className="kc-muted-note kc-export-error">
              {slice.note || 'KimCad couldn’t slice this part.'}
            </p>
          )}
          {slice && slice.sliced && (
            <>
              <PrintSummary
                slice={slice}
                slotMaterials={isMultiHead ? slotMaterialNames : undefined}
              />
              {/* Stage 10: direct print — only offered once a proven print file exists; the
                  server re-checks the gate verdict on /api/send regardless. */}
              <SendPanel designId={designId} />
            </>
          )}
        </>
      )}

      {result.mesh_url && (
        <div className="kc-formats">
          <a className="kc-download-model" href={result.mesh_url} download>
            Download 3D model (.STL)
          </a>
          {result.step_url && (
            <a className="kc-download-model kc-download-step" href={result.step_url} download>
              Download editable CAD (.STEP)
            </a>
          )}
          {result.step_url ? (
            <p className="kc-muted-note kc-formats-note">
              The <strong>.STL</strong> opens in other slicers and CAD tools. The{' '}
              <strong>.STEP</strong> is the editable, precision CAD model — open it in any CAD
              program to keep modeling; it&rsquo;s the as-designed shape, so print orientation is
              applied only to the printable mesh. The first download takes a few seconds while
              KimCad prepares it. Once you slice, you&rsquo;ll also get a printer-agnostic{' '}
              <strong>.3mf</strong> that&rsquo;s safe to share.
            </p>
          ) : result.step_offer === 'settings' ? (
            // KC-11 (#15): this part CAN export editable CAD — the engine just isn't
            // installed. Say exactly where to turn it on instead of dangling a dead promise.
            <p className="kc-muted-note kc-formats-note">
              The <strong>.STL</strong> opens in other slicers and CAD tools, and once you slice
              you&rsquo;ll get a printer-agnostic <strong>.3mf</strong> that&rsquo;s safe to share.
              Want an editable, precision CAD file (<strong>.STEP</strong>) of this part too?{' '}
              <a className="kc-link-btn" href="#/settings">
                Enable the CAD export engine in Settings
              </a>{' '}
              — a one-time setup.
            </p>
          ) : (
            <p className="kc-muted-note kc-formats-note">
              The <strong>.STL</strong> opens in other slicers and CAD tools, and once you slice
              you&rsquo;ll get a printer-agnostic <strong>.3mf</strong> that&rsquo;s safe to share.
              KimCad&rsquo;s standard parts can also export an editable <strong>.STEP</strong>{' '}
              when the CAD export engine is enabled (see Settings); this part was built by the
              experimental generator, which exports .STL only.
            </p>
          )}
        </div>
      )}
    </section>
  )
}

// Slice 10 — output clarity: once the part is sliced, show *what you're going to get* — a plain
// "your design → print file" line, the estimate broken out (time / layers / filament length +
// weight) instead of one blob, and the print file with a copy-the-link affordance.
function PrintSummary({
  slice,
  slotMaterials,
}: {
  slice: SliceResponse
  // UX-004: per-extruder material display names for a multi-head printer (in slot order).
  // Undefined/empty for a single head — the summary keeps showing the one primary material.
  slotMaterials?: string[]
}) {
  const [copied, setCopied] = useState(false)
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(
    () => () => {
      if (copyTimer.current) clearTimeout(copyTimer.current)
    },
    [],
  )

  const rows = buildEstimateRows(slice.estimate_detail)
  // Only caption the weight as estimated when there's actually a weight row to caption — keeps
  // the note from ever appearing orphaned (defence in depth alongside the backend's volume guard).
  const showEstNote =
    !!slice.estimate_detail?.filament_g_estimated && rows.some((r) => r.key === 'weight')
  const fileUrl = slice.gcode_url ?? null
  // An absolute URL is what's useful to paste elsewhere (another tab, a printer's web UI). Fall
  // back to the raw value if there's no window (tests/SSR).
  const absoluteUrl =
    fileUrl && typeof window !== 'undefined'
      ? new URL(fileUrl, window.location.origin).href
      : fileUrl

  async function copyLink() {
    if (!absoluteUrl) return
    try {
      await navigator.clipboard.writeText(absoluteUrl)
      setCopied(true)
      if (copyTimer.current) clearTimeout(copyTimer.current)
      copyTimer.current = setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard blocked (no permission / insecure context) — the download link still works */
    }
  }

  // UX-004: a multi-head slice lists each extruder's filament ("Extruder 1: PLA, Extruder 2: TPU")
  // instead of the single primary material — what actually went on the machine, per slot.
  const hasSlots = !!slotMaterials && slotMaterials.length > 0
  const slotLead = hasSlots
    ? ` — ${slotMaterials.map((name, i) => `Extruder ${i + 1}: ${name}`).join(', ')}`
    : slice.material
      ? ` in ${slice.material}`
      : ''

  return (
    <div className="kc-slice-result">
      <p className="kc-print-lead">
        Sliced{slice.printer ? ` for ${slice.printer}` : ''}
        {slotLead}. Here&rsquo;s your print:
      </p>
      <ol className="kc-print-flow" aria-label="From your design to a ready print file">
        <li className="kc-flow-step kc-flow-done">Your design</li>
        <li className="kc-flow-step kc-flow-done">Sliced</li>
        <li className="kc-flow-step kc-flow-done">Print file ready</li>
      </ol>

      {rows.length > 0 ? (
        <>
          <dl className="kc-print-stats">
            {rows.map((r) => (
              <div className="kc-print-stat" key={r.key}>
                <dt>{r.label}</dt>
                <dd className="kc-mono">{r.value}</dd>
              </div>
            ))}
          </dl>
          {showEstNote && (
            <p className="kc-muted-note kc-est-note">
              Weight is estimated from the print volume — your actual filament&rsquo;s density may
              differ.
            </p>
          )}
        </>
      ) : slice.estimate ? (
        <p className="kc-muted-note">{slice.estimate}</p>
      ) : (
        <p className="kc-muted-note">This printer profile didn&rsquo;t report a print estimate.</p>
      )}

      {fileUrl && (
        <div className="kc-print-file">
          <a
            className="kc-btn kc-btn-dark kc-download"
            href={fileUrl}
            download={slice.gcode_filename}
          >
            Download print file (.3mf)
          </a>
          <button
            type="button"
            className="kc-btn kc-btn-ghost kc-copy-link"
            onClick={copyLink}
            disabled={!absoluteUrl}
          >
            {copied ? 'Copied!' : 'Copy link'}
          </button>
          <span className="kc-sr-only" role="status" aria-live="polite">
            {copied ? 'Link copied to clipboard' : ''}
          </span>
        </div>
      )}
      {slice.gcode_filename && <p className="kc-file-name kc-mono">{slice.gcode_filename}</p>}
    </div>
  )
}
