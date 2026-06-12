import { useEffect, useRef, useState } from 'react'
import { DESIGN_PHASES, phaseLabel, phaseStep } from '../designPhase'
import { useUnits } from '../useUnits'
import {
  type Dimensions,
  type HighlightRisk,
  type MeasureState,
  KCViewport,
} from '../viewport/KCViewport'

// React wrapper around the vanilla KCViewport. It owns the viewport's lifecycle, loads the real
// mesh from `meshUrl` (served at /api/mesh/<id>), and surfaces the print-aware affordances: the
// W/D/H dimension pills (positioned by KCViewport each frame), an orientation chip, a drag hint,
// and a dimensions-aware aria-label. `busy` is the design call in flight before a mesh exists.
function fmtElapsed(s: number): string {
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.max(0, s) % 60).padStart(2, '0')}`
}

export default function Viewport({
  meshUrl,
  busy,
  restoring,
  busyElapsed,
  busyPhase = null,
  onCancelDesign,
  onModelReady,
  highlights = [],
  showHighlights = true,
  focus = null,
}: {
  meshUrl: string | null
  busy: boolean
  // `restoring` = reopening a saved design (a fast load), as opposed to a model design run. The two
  // share `busy` but get different overlays: a reopen shows a plain "Reopening…" (no timer/Cancel),
  // a design run shows the cancelable, elapsed-timed overlay.
  restoring: boolean
  // Live elapsed seconds while a design runs, and a cancel hook — so the "Designing…" screen shows
  // progress and is never a trap (the local model can run for minutes).
  busyElapsed: number
  // MS-3: the current run's phase (planning/generating/rendering/validating), or null before the
  // first phase is reported — drives the live step label + stepper on the "Designing…" screen.
  busyPhase?: string | null
  onCancelDesign: () => void
  // Stage 8.5: fired after a mesh is framed, handing back a thumbnail-capture fn so the app can
  // snapshot the rendered part (for the "My Designs" gallery) at the moment it's on screen.
  onModelReady?: (capture: () => string | null) => void
  // Slice 8: problem highlights to show ON the model, a visibility toggle, and a focus request
  // ({id, nonce} so repeated clicks re-focus). KCViewport aligns highlights to the mesh transform.
  highlights?: HighlightRisk[]
  showHighlights?: boolean
  focus?: { id: string; n: number } | null
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
  // UI-v2 slice 4 (#23): the click-to-measure tool — mode + the live readout from the engine.
  const [measuring, setMeasuring] = useState(false)
  const [measure, setMeasure] = useState<MeasureState | null>(null)
  const { formatMm, unit } = useUnits()
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

  // Slice 8: push problem highlights to the engine. KCViewport re-applies them against the mesh
  // transform on the next load too, so order (highlights vs mesh) doesn't matter.
  useEffect(() => {
    vpRef.current?.setHighlights(highlights)
  }, [highlights])

  useEffect(() => {
    vpRef.current?.setHighlightsVisible(showHighlights)
  }, [showHighlights])

  // Focus the requested problem region; `focus.n` changes on every click so re-focus works.
  useEffect(() => {
    if (focus) vpRef.current?.focusHighlight(focus.id)
  }, [focus])

  const showModel = hasModel && !busy && error === null
  // The full-cover overlay is for when there's NO model to show: the initial design call, the
  // first render, a hard load error, or the empty state. A re-render (model already framed) swaps
  // quietly underneath — no overlay.
  // The busy (model-in-flight) state gets its own rich overlay below (message + timer + Cancel);
  // this string overlay is for the remaining no-model states.
  const overlay =
    loading && !hasModel
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
          {/* UI-v2 slice 4: the click-to-measure tool. Toggle on -> two surface clicks give
              the straight-line distance + per-axis deltas (in the display unit). */}
          {showModel && (
            <button
              type="button"
              className={`kc-measure-toggle${measuring ? ' kc-measure-toggle-on' : ''}`}
              aria-pressed={measuring}
              onClick={() => {
                const next = !measuring
                setMeasuring(next)
                setMeasure(null)
                vpRef.current?.setMeasureMode(next, next ? setMeasure : null)
              }}
            >
              {measuring ? 'Measuring — click two points' : 'Measure'}
            </button>
          )}
          {showModel && measuring && measure && (
            <span className="kc-measure-readout" role="status">
              {measure.points === 0 ? (
                'That click missed the part — click on the part itself'
              ) : measure.distanceMm === null ? (
                'Point 1 set — click the second point'
              ) : (
                <>
                  <strong>{formatMm(measure.distanceMm)} {unit}</strong>
                  {measure.deltasMm && (
                    <span className="kc-measure-deltas">
                      {' '}ΔX {formatMm(measure.deltasMm[0])} · ΔY {formatMm(measure.deltasMm[1])} ·
                      ΔZ {formatMm(measure.deltasMm[2])}
                    </span>
                  )}
                </>
              )}
            </span>
          )}
          {showModel && (
            <span className="kc-viewport-hint">
              {measuring ? 'Click the part to measure · drag still rotates' : 'Drag to rotate · scroll to zoom'}
            </span>
          )}
          {showModel && staleNote && (
            <span className="kc-viewport-stale" role="status">
              Preview couldn&rsquo;t update — refine to regenerate this version.
            </span>
          )}
          {busy && restoring ? (
            <div className="kc-viewport-overlay kc-viewport-restoring" role="status">
              <span className="kc-spin kc-spin-lg" aria-hidden="true" />
              <span>Reopening your design…</span>
            </div>
          ) : busy ? (
            <div className="kc-viewport-overlay kc-viewport-busy" role="status">
              <span className="kc-spin kc-spin-lg" aria-hidden="true" />
              <div className="kc-busy-title">Designing your part…</div>
              {/* MS-3: the live step. aria-live polite so a screen reader announces each phase
                  change (infrequent — 4 over minutes), unlike the per-second elapsed tick. */}
              {phaseLabel(busyPhase) && (
                <div className="kc-busy-phase" aria-live="polite">{phaseLabel(busyPhase)}</div>
              )}
              {phaseStep(busyPhase) > 0 && (
                <ol className="kc-busy-steps" aria-hidden="true">
                  {DESIGN_PHASES.map((p, i) => {
                    const cur = phaseStep(busyPhase)
                    const state = i + 1 < cur ? 'done' : i + 1 === cur ? 'active' : 'todo'
                    return <li key={p} className={`kc-busy-step kc-busy-step-${state}`} />
                  })}
                </ol>
              )}
              <p className="kc-busy-sub">
                This runs on your computer&rsquo;s AI — it can take a few minutes, especially for a
                brand-new shape. Nothing leaves your machine.
              </p>
              {/* aria-hidden: the ~2 Hz tick would otherwise chant in a screen reader (UX-801). */}
              <div className="kc-busy-elapsed" aria-hidden="true">{fmtElapsed(busyElapsed)} elapsed</div>
              <button
                type="button"
                className="kc-btn kc-busy-cancel"
                onClick={onCancelDesign}
              >
                Cancel
              </button>
            </div>
          ) : overlay ? (
            <div
              className={`kc-viewport-overlay${error ? ' kc-viewport-overlay-error' : ''}`}
              role="status"
            >
              {overlay}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
