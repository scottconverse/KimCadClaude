import { useEffect, useRef, useState } from 'react'
import { KCViewport } from '../viewport/KCViewport'

// React wrapper around the vanilla KCViewport. It owns the viewport's lifecycle and loads the
// real mesh from `meshUrl` (served at /api/mesh/<id>); `busy` is the design call in flight
// before a mesh exists. Overlays cover the three honest states: designing, rendering, empty.
export default function Viewport({ meshUrl, busy }: { meshUrl: string | null; busy: boolean }) {
  const stageRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const vpRef = useRef<KCViewport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!stageRef.current || !canvasRef.current) return
    const vp = new KCViewport(stageRef.current, canvasRef.current)
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
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    vp.loadMesh(meshUrl)
      .then(() => {
        if (!cancelled) setLoading(false)
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

  const overlay = busy
    ? 'Designing your part…'
    : loading
      ? 'Rendering…'
      : error
        ? error
        : !meshUrl
          ? 'Your 3D preview appears here.'
          : null

  return (
    <div className="kc-col-center">
      <div className="kc-viewport-card">
        <div className="kc-viewport-stage" ref={stageRef}>
          <canvas ref={canvasRef} className="kc-viewport-canvas" aria-label="3D preview" />
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
