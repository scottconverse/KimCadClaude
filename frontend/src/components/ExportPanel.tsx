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

// Export & print (Stage 4, Slice 5): pick a printer + material, slice the already-validated,
// oriented mesh on confirmation, and download the proven G-code (or the model). Gate-aware — a
// part that failed the printability gate can't be sliced (the server refuses too), but the model
// stays downloadable to inspect. The full direct-print/send UI is Stage 10.
export default function ExportPanel({ result }: { result: DesignResponse | null }) {
  const [options, setOptions] = useState<OptionsResponse | null>(null)
  const [printer, setPrinter] = useState('')
  const [material, setMaterial] = useState('')
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

  // A new design clears the previous slice result.
  useEffect(() => {
    setSlice(null)
    setError(null)
  }, [result?.mesh_url])

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
      setSlice(await postSlice(designId, printer, selectedMaterial, controller.signal))
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
      <ConnectorStatus />

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
          {slice && slice.sliced && <PrintSummary slice={slice} />}
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
              <strong>.STEP</strong> is the editable, precision CAD model (CadQuery) — open it in
              any CAD program to keep modeling; it&rsquo;s the as-designed shape, so print
              orientation is applied only to the printable mesh. Once you slice, you&rsquo;ll also
              get a printer-agnostic <strong>.3mf</strong> that&rsquo;s safe to share.
            </p>
          ) : (
            <p className="kc-muted-note kc-formats-note">
              The <strong>.STL</strong> opens in other slicers and CAD tools, and once you slice
              you&rsquo;ll get a printer-agnostic <strong>.3mf</strong> that&rsquo;s safe to share.
              KimCad picks the geometry engine to fit each part (shown on the printability check
              above); parts built with the precision CAD engine (CadQuery) also offer an editable{' '}
              <strong>.STEP</strong> export.
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
function PrintSummary({ slice }: { slice: SliceResponse }) {
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

  return (
    <div className="kc-slice-result">
      <p className="kc-print-lead">
        Sliced{slice.printer ? ` for ${slice.printer}` : ''}
        {slice.material ? ` in ${slice.material}` : ''}. Here&rsquo;s your print:
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
