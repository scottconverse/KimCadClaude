import { useEffect, useMemo, useState } from 'react'
import {
  designIdFromMeshUrl,
  getOptions,
  postSlice,
  type DesignResponse,
  type OptionsResponse,
  type SliceResponse,
} from '../api'
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
    setSlicing(true)
    setError(null)
    setSlice(null)
    try {
      setSlice(await postSlice(designId, printer, selectedMaterial))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Slicing failed.')
    } finally {
      setSlicing(false)
    }
  }

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
    <section className="kc-card">
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

          <button
            type="button"
            className="kc-btn kc-btn-accent kc-slice-btn"
            onClick={handleSlice}
            disabled={!canSlice}
          >
            {slicing ? 'Slicing…' : 'Slice & prepare file'}
          </button>

          {error !== null && <p className="kc-muted-note kc-export-error">{error}</p>}
          {slice && !slice.sliced && (
            <p className="kc-muted-note kc-export-error">
              {slice.note || 'KimCad couldn’t slice this part.'}
            </p>
          )}
          {slice && slice.sliced && (
            <div className="kc-slice-result">
              {slice.estimate && <p className="kc-muted-note">{slice.estimate}</p>}
              {slice.gcode_url && (
                <a className="kc-btn kc-btn-dark kc-download" href={slice.gcode_url}>
                  Download G-code
                </a>
              )}
            </div>
          )}
        </>
      )}

      {result.mesh_url && (
        <a className="kc-download-model" href={result.mesh_url} download>
          Download 3D model (STL)
        </a>
      )}
    </section>
  )
}
