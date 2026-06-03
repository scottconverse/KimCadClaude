import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import {
  designIdFromMeshUrl,
  postDesign,
  postRender,
  reopenDesign,
  saveDesign,
  type DesignResponse,
} from './api'
import Landing from './components/Landing'
import MyDesigns from './components/MyDesigns'
import Topbar from './components/Topbar'
import { useHashRoute } from './useHashRoute'

// The workspace pulls in three.js (the viewport). Code-split it so the landing screen loads
// without the 3D bundle; three is fetched the first time a part is designed.
const Workspace = lazy(() => import('./components/Workspace'))

// Minimum time the "Re-rendering…" note stays up, so a sub-second render reads as a deliberate
// signal rather than a flicker (UX-003).
const RERENDER_MIN_DWELL_MS = 350
// Debounce window for re-saving a design after a slider change, so a rapid drag persists once.
const RESAVE_DEBOUNCE_MS = 800

// KimCad SPA — application shell + the design flow.
//
// Stage 8.5 Slice 1: the app now has routes (`#/`, `#/designs`, `#/design/<id>`) and persists work.
// A completed design auto-saves to the local "My Designs" library and the URL becomes
// `#/design/<id>`, so a refresh restores it (no more lost work). Slider changes re-save the same
// entry (debounced). The library is reachable from the Topbar.
export default function App() {
  const { route, navigate } = useHashRoute()
  const [prompt, setPrompt] = useState('')
  const [result, setResult] = useState<DesignResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rerendering, setRerendering] = useState(false)
  const [rerenderError, setRerenderError] = useState<string | null>(null)
  const renderSeq = useRef(0)
  const resultRef = useRef<DesignResponse | null>(null)
  resultRef.current = result
  // The latest viewport thumbnail-capture fn (handed over when a part is framed).
  const captureRef = useRef<(() => string | null) | null>(null)
  const resaveTimer = useRef<number | null>(null)
  // Guards a create-save in flight, so a re-render during the initial save can't start a second
  // create (which would spawn a duplicate library entry). The in-flight create sets saved_id;
  // subsequent re-renders then re-save the single entry.
  const creatingRef = useRef(false)
  // L-2 (wiring-audit): set when a design is freshly reopened/restored, so the model-ready that
  // follows doesn't fire a redundant re-save of unchanged, already-saved work. Cleared on the next
  // frame or a new design; an actual edit (re-render) re-saves normally.
  const restoredRef = useRef(false)
  // UX-001: a visible save indicator so the user can SEE auto-save work, instead of wondering
  // whether their part survived. 'saving' is transient; once persisted the Topbar shows a resting
  // "Saved · My Designs" (driven by result.saved_id); 'error' self-heals via one delayed retry.
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const retryRef = useRef<number | null>(null)
  // Latest persist fn, so the error-retry timer can re-invoke it without a self-referential closure.
  const persistRef = useRef<((opts?: { immediate?: boolean }) => Promise<void>) | null>(null)

  const applyResult = useCallback((r: DesignResponse | null) => {
    resultRef.current = r
    setResult(r)
  }, [])

  // --- save / persistence -------------------------------------------------
  // Persist the current design. A first save (no saved_id) creates a library entry and routes to
  // `#/design/<id>`; a later save updates that entry in place. Best-effort — a save failure leaves
  // the live part untouched (it just isn't persisted yet).
  const persist = useCallback(
    async (opts?: { immediate?: boolean }) => {
      const r = resultRef.current
      if (!r || !r.has_mesh) return
      const designId = designIdFromMeshUrl(r.mesh_url)
      if (designId == null) return
      const thumb = captureRef.current?.() ?? null
      const isCreate = !r.saved_id
      const run = async () => {
        // Don't start a second create while one is in flight (avoids a duplicate library entry).
        if (isCreate && creatingRef.current) return
        if (isCreate) creatingRef.current = true
        setSaveState('saving')
        try {
          const saved = await saveDesign(designId, '', thumb, r.saved_id)
          // Mark the result as saved + give it a durable URL (only on the first save).
          if (
            resultRef.current &&
            resultRef.current.mesh_url === r.mesh_url &&
            !resultRef.current.saved_id
          ) {
            applyResult({ ...resultRef.current, saved_id: saved.id })
            navigate(`design/${saved.id}`, { replace: true })
          }
          setSaveState('saved')
        } catch {
          // Best-effort: a save failure is non-fatal (the live part is untouched). Surface it
          // (UX-001) and schedule a single delayed retry so a transient miss self-heals.
          setSaveState('error')
          if (retryRef.current === null) {
            retryRef.current = window.setTimeout(() => {
              retryRef.current = null
              void persistRef.current?.({ immediate: true })
            }, 1500)
          }
        } finally {
          if (isCreate) creatingRef.current = false
        }
      }
      if (opts?.immediate || !r.saved_id) {
        await run()
      } else {
        if (resaveTimer.current !== null) window.clearTimeout(resaveTimer.current)
        resaveTimer.current = window.setTimeout(run, RESAVE_DEBOUNCE_MS)
      }
    },
    [applyResult, navigate],
  )
  persistRef.current = persist

  // The viewport frames a part -> capture it and persist (create on the first frame, debounced
  // re-save on a re-render).
  const handleModelReady = useCallback(
    (capture: () => string | null) => {
      captureRef.current = capture
      // L-2: a just-restored design is already saved + unchanged — don't re-save it merely because
      // the viewport framed it. The next real edit (a re-render) clears this and re-saves normally.
      if (restoredRef.current) {
        restoredRef.current = false
        return
      }
      void persist()
    },
    [persist],
  )

  // --- design / re-render -------------------------------------------------
  function resetSaveIndicator() {
    if (resaveTimer.current !== null) window.clearTimeout(resaveTimer.current)
    if (retryRef.current !== null) {
      window.clearTimeout(retryRef.current)
      retryRef.current = null
    }
    restoredRef.current = false
    setSaveState('idle')
  }

  async function handleSubmit(submitted: string) {
    resetSaveIndicator()
    navigate('', { replace: true }) // a brand-new design has no saved id yet
    setPrompt(submitted)
    applyResult(null)
    setError(null)
    setRerenderError(null)
    setRerendering(false)
    renderSeq.current++ // abandon any in-flight re-render of the previous design
    setBusy(true)
    try {
      applyResult(await postDesign(submitted))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  async function handleRerender(values: Record<string, number>) {
    const designId = designIdFromMeshUrl(resultRef.current?.mesh_url)
    if (designId == null) return
    const seq = ++renderSeq.current
    const startedAt = performance.now()
    setRerendering(true)
    setRerenderError(null)
    try {
      const next = await postRender(designId, values)
      if (seq === renderSeq.current) {
        // Carry the saved_id forward so a re-render of a saved design re-saves the same entry.
        applyResult({ ...next, saved_id: resultRef.current?.saved_id })
      }
    } catch (err) {
      if (seq === renderSeq.current) {
        setRerenderError(err instanceof Error ? err.message : 'Re-render failed.')
      }
    } finally {
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
    resetSaveIndicator()
    navigate('', { replace: true })
    setPrompt('')
    applyResult(null)
    setError(null)
    setRerenderError(null)
    setRerendering(false)
    renderSeq.current++
    setBusy(false)
  }

  // Restore a saved design when the route points at one we don't already have loaded (a fresh
  // page load on `#/design/<id>`, or opening one from the library).
  useEffect(() => {
    if (route.name !== 'design') return
    if (resultRef.current?.saved_id === route.id) return
    let cancelled = false
    renderSeq.current++ // abandon any in-flight re-render of a previous design
    setBusy(true)
    setError(null)
    setRerenderError(null)
    reopenDesign(route.id)
      .then((r) => {
        if (cancelled) return
        setPrompt(r.prompt ?? '')
        applyResult(r)
        restoredRef.current = true // L-2: skip the redundant re-save on the restore's model-ready
      })
      .catch(() => {
        if (!cancelled) setError("That design couldn't be opened.")
      })
      .finally(() => {
        if (!cancelled) setBusy(false)
      })
    return () => {
      cancelled = true
    }
  }, [route, applyResult])

  const meshUrl = result?.has_mesh && result.mesh_url ? result.mesh_url : null
  const onWorkspace = route.name !== 'designs' && (result !== null || busy || route.name === 'design')

  return (
    <div className="kc-shell">
      <Topbar
        showNewDesign={onWorkspace}
        onNewDesign={handleNewDesign}
        onMyDesigns={() => navigate('designs')}
        activeRoute={route.name}
        saveState={saveState}
        savedId={result?.saved_id ?? null}
      />
      {route.name === 'designs' ? (
        <MyDesigns onOpen={(id) => navigate(`design/${id}`)} onNew={handleNewDesign} />
      ) : !onWorkspace ? (
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
            onModelReady={handleModelReady}
          />
        </Suspense>
      )}
    </div>
  )
}
