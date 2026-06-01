import { useEffect, useRef, useState } from 'react'
import { KCViewport, type Dimensions } from '../viewport/KCViewport'

// React wrapper around the vanilla KCViewport. It owns the viewport's lifecycle, loads the real
// mesh from `meshUrl` (served at /api/mesh/<id>), and surfaces the print-aware affordances: the
// W/D/H dimension pills (positioned by KCViewport each frame), an orientation chip, a drag hint,
// and a dimensions-aware aria-label. `busy` is the design call in flight before a mesh exists.
export default function Viewport({ meshUrl, busy }: { meshUrl: string | null; busy: boolean }) {
  const stageRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const labelX = useRef<HTMLSpanElement>(null)
  const labelY = useRef<HTMLSpanElement>(null)
  const labelZ = useRef<HTMLSpanElement>(null)
  const vpRef = useRef<KCViewport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dims, setDims] = useState<Dimensions | null>(null)

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
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    vp.loadMesh(meshUrl)
      .then(() => {
        if (!cancelled) {
          setLoading(false)
          setDims(vp.getDimensions())
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoading(false)
          setError('Could not load the 3D preview.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [meshUrl])

  const showModel = !busy && !loading && error === null && meshUrl !== null
  const overlay = busy
    ? 'Designing your part…'
    : loading
      ? 'Rendering…'
      : error
        ? error
        : !meshUrl
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
