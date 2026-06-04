import { useEffect, useRef, useState } from 'react'
import { KCViewport, type Dimensions } from '../viewport/KCViewport'

// React wrapper around the vanilla KCViewport. It owns the viewport's lifecycle, loads the real
// mesh from `meshUrl` (served at /api/mesh/<id>), and surfaces the print-aware affordances: the
// W/D/H dimension pills (positioned by KCViewport each frame), an orientation chip, a drag hint,
// and a dimensions-aware aria-label. `busy` is the design call in flight before a mesh exists.
export default function Viewport({
  meshUrl,
  busy,
  onModelReady,
}: {
  meshUrl: string | null
  busy: boolean
  // Stage 8.5: fired after a mesh is framed, handing back a thumbnail-capture fn so the app can
  // snapshot the rendered part (for the "My Designs" gallery) at the moment it's on screen.
  onModelReady?: (capture: () => string | null) => void
}) {
  const stageRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const labelX = useRef<HTMLSpanElement>(null)
  const labelY = useRef<HTMLSpanElement>(null)
  const labelZ = useRef<HTMLSpanElement>(null)
  const vpRef = useRef<KCViewport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dims, setDims] = useState<Dimensions | null>(null)
  // Whether a part is currently framed on screen. KCViewport.loadMesh swaps the mesh atomically
  // (it awaits the new geometry, THEN replaces the old one), so during a live-slider re-render the
  // previous part stays visible. While a model is shown we suppress the full-cover "Rendering…"
  // overlay — the swap is quiet (the parameters card shows the "Updating…" note instead).
  const [hasModel, setHasModel] = useState(false)
  // ENG-004: a non-blocking note for when a mesh load fails while a part is already on screen —
  // e.g. switching to an older version whose server-side mesh was LRU-evicted. We keep the framed
  // part (no crash, the right-panel data is intact) but tell the user the preview may be stale.
  const [staleNote, setStaleNote] = useState(false)

  useEffect(() => {
    if (!stageRef.current || !canvasRef.current) return
    const labels =
      labelX.current && labelY.current && labelZ.current
        ? { x: labelX.current, y: labelY.current, z: labelZ.current }
        : null
    const vp = new KCViewport(stageRef.current, canvasRef.current, labels)
    vpRef.current = vp
    return () => {
      vp.dispose()
      vpRef.current = null
    }
  }, [])

  useEffect(() => {
    const vp = vpRef.current
    if (!vp) return
    if (!meshUrl) {
      vp.clearModel()
      setError(null)
      setDims(null)
      setHasModel(false)
      setStaleNote(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    vp.loadMesh(meshUrl)
      .then(() => {
        if (!cancelled) {
          setLoading(false)
          setStaleNote(false)
          setDims(vp.getDimensions())
          setHasModel(true)
          // The part is framed — hand the app a capture fn it can call to snapshot it.
          onModelReady?.(() => vp.captureThumbnail())
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoading(false)
          // The previous mesh is still on screen (the swap only happens on a successful load), so
          // only surface a blocking error when there's nothing to fall back to. If a part IS framed,
          // keep it but flag that this preview couldn't load (ENG-004 — e.g. an evicted version).
          if (!hasModel) setError('Could not load the 3D preview.')
          else setStaleNote(true)
        }
      })
    return () => {
      cancelled = true
    }
    // Keyed on `meshUrl` only. `hasModel` is read in the failure branch but deliberately omitted
    // from the deps — re-running on a model landing would reload the same mesh; the closure's
    // captured value (set by the prior load, guarded by `cancelled`) is correct here.
  }, [meshUrl])

  const showModel = hasModel && !busy && error === null
  // The full-cover overlay is for when there's NO model to show: the initial design call, the
  // first render, a hard load error, or the empty state. A re-render (model already framed) swaps
  // quietly underneath — no overlay.
  const overlay = busy
    ? 'Designing your part…'
    : loading && !hasModel
      ? 'Rendering…'
      : error && !hasModel
        ? error
        : !meshUrl && !hasModel
          ? 'Your 3D preview appears here.'
          : null
  const ariaLabel = dims
    ? `3D preview — ${dims.x} by ${dims.y} by ${dims.z} millimetres`
    : '3D preview'

  return (
    <div className="kc-col-center">
      <div className="kc-viewport-card">
        <div className="kc-viewport-stage" ref={stageRef}>
          <canvas ref={canvasRef} className="kc-viewport-canvas" aria-label={ariaLabel} />
          {/* Dimension pills — KCViewport projects the part's bbox and positions/fills these. */}
          <span ref={labelX} className="kc-dim-pill" aria-hidden="true" />
          <span ref={labelY} className="kc-dim-pill" aria-hidden="true" />
          <span ref={labelZ} className="kc-dim-pill" aria-hidden="true" />
          {showModel && (
            <span className="kc-viewport-chip">Auto-oriented · plate-down</span>
          )}
          {showModel && (
            <span className="kc-viewport-hint">Drag to rotate · scroll to zoom</span>
          )}
          {showModel && staleNote && (
            <span className="kc-viewport-stale" role="status">
              Preview couldn&rsquo;t update — refine to regenerate this version.
            </span>
          )}
          {overlay && (
            <div
              className={`kc-viewport-overlay${error ? ' kc-viewport-overlay-error' : ''}`}
              role="status"
            >
              {overlay}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
