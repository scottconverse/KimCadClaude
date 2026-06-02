import { lazy, Suspense, useRef, useState } from 'react'
import Topbar from './components/Topbar'
import Landing from './components/Landing'
import { designIdFromMeshUrl, postDesign, postRender, type DesignResponse } from './api'

// The workspace pulls in three.js (the viewport). Code-split it so the landing screen loads
// without the 3D bundle; three is fetched the first time a part is designed.
const Workspace = lazy(() => import('./components/Workspace'))

// Minimum time the "Re-rendering…" note stays up, so a sub-second render reads as a deliberate
// signal rather than a flicker (UX-003).
const RERENDER_MIN_DWELL_MS = 350

// KimCad SPA — application shell + the design flow.
//
// Stage 4: landing → describe → the part renders in the Three.js viewport (Slice 3); the
// conversation, plan, and printability report fill in from /api/design (Slice 4); and the
// printer/material → slice → download + connector status panel is wired (Slice 5). Live
// parameter sliders are Stage 5 (the deterministic template engine); browser send is Stage 10.
export default function App() {
  const [view, setView] = useState<'landing' | 'workspace'>('landing')
  const [prompt, setPrompt] = useState('')
  const [result, setResult] = useState<DesignResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Live-slider re-render state (Stage 5). `rerendering` drives the quiet "Updating…" note in the
  // parameters card (the viewport keeps the last mesh until the new one lands); `rerenderError`
  // surfaces a failed re-render without tearing down the last good result.
  const [rerendering, setRerendering] = useState(false)
  const [rerenderError, setRerenderError] = useState<string | null>(null)
  // Monotonic token so an out-of-order re-render response (a slow render that resolves after a
  // newer one) can't clobber the latest geometry — only the most recent request applies.
  const renderSeq = useRef(0)
  // The latest result, read inside the async re-render without making it a dependency.
  const resultRef = useRef<DesignResponse | null>(null)
  resultRef.current = result

  async function handleSubmit(submitted: string) {
    setView('workspace')
    setPrompt(submitted)
    setResult(null)
    setError(null)
    setRerenderError(null)
    setRerendering(false) // an abandoned re-render (below) won't clear its own flag — reset it here
    renderSeq.current++ // abandon any in-flight re-render of the previous design
    setBusy(true)
    try {
      setResult(await postDesign(submitted))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  // Deterministic local re-render at new slider values — no model call. Debounced by the
  // parameters card; this applies the server's clamped result (and ignores stale responses).
  async function handleRerender(values: Record<string, number>) {
    const designId = designIdFromMeshUrl(resultRef.current?.mesh_url)
    if (designId == null) return
    const seq = ++renderSeq.current
    const startedAt = performance.now()
    setRerendering(true)
    setRerenderError(null)
    try {
      const next = await postRender(designId, values)
      if (seq === renderSeq.current) setResult(next)
    } catch (err) {
      if (seq === renderSeq.current) {
        setRerenderError(err instanceof Error ? err.message : 'Re-render failed.')
      }
    } finally {
      // UX-003: hold the "Re-rendering…" note for a minimum dwell so a sub-second render reads as
      // a deliberate signal, not a flicker. Only the latest re-render clears the flag (seq guard).
      if (seq === renderSeq.current) {
        const remaining = RERENDER_MIN_DWELL_MS - (performance.now() - startedAt)
        if (remaining > 0) {
          window.setTimeout(() => {
            if (seq === renderSeq.current) setRerendering(false)
          }, remaining)
        } else {
          setRerendering(false)
        }
      }
    }
  }

  function handleNewDesign() {
    setView('landing')
    setPrompt('')
    setResult(null)
    setError(null)
    setRerenderError(null)
    setRerendering(false) // clear the flag the abandoned re-render (below) would otherwise leave on
    renderSeq.current++ // abandon any in-flight re-render
    setBusy(false)
  }

  const meshUrl = result?.has_mesh && result.mesh_url ? result.mesh_url : null

  return (
    <div className="kc-shell">
      <Topbar showNewDesign={view === 'workspace'} onNewDesign={handleNewDesign} />
      {view === 'landing' ? (
        <Landing onSubmit={handleSubmit} busy={busy} />
      ) : (
        <Suspense fallback={<div className="kc-workspace-loading">Loading workspace…</div>}>
          <Workspace
            prompt={prompt}
            result={result}
            meshUrl={meshUrl}
            busy={busy}
            error={error}
            rerendering={rerendering}
            rerenderError={rerenderError}
            onRerender={handleRerender}
          />
        </Suspense>
      )}
    </div>
  )
}
