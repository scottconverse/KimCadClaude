import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import {
  designIdFromMeshUrl,
  postDesign,
  postRender,
  reopenDesign,
  saveDesign,
  type ChatTurn,
  type DesignResponse,
  type Message,
} from './api'
import { assistantMessage, isFailureStatus } from './designStatus'
import Landing from './components/Landing'
import MyDesigns from './components/MyDesigns'
import Topbar from './components/Topbar'
import { useHashRoute } from './useHashRoute'

// The workspace pulls in three.js (the viewport). Code-split it so the landing screen loads
// without the 3D bundle; three is fetched the first time a part is designed.
const Workspace = lazy(() => import('./components/Workspace'))

const RERENDER_MIN_DWELL_MS = 350
const RESAVE_DEBOUNCE_MS = 800

// KimCad SPA — application shell + the design flow.
// Stage 8.5 Slice 2: the app now maintains a multi-turn conversation thread. Each user prompt
// and assistant reply is appended as a Message, so the chat panel renders a real conversation.
// A "Refine your part" input in the workspace lets the user add follow-up turns ("make it 10mm
// taller") that thread the prior conversation into the model for context. Clarifying questions
// are answered inline — the answer continues from the same thread.
export default function App() {
  const { route, navigate } = useHashRoute()

  // Slice 2: the full conversation thread (all user + assistant turns for this design session).
  // A new design resets this; a follow-up refine/clarify appends to it.
  const [messages, setMessages] = useState<Message[]>([])
  // The most recent completed design result — drives the viewport + right panel.
  const [result, setResult] = useState<DesignResponse | null>(null)
  const [busy, setBusy] = useState(false)
  // A top-level network/unexpected error (not a pipeline status failure — those surface as
  // assistant messages with error tone in the thread).
  const [error, setError] = useState<string | null>(null)
  const [rerendering, setRerendering] = useState(false)
  const [rerenderError, setRerenderError] = useState<string | null>(null)
  const renderSeq = useRef(0)
  const resultRef = useRef<DesignResponse | null>(null)
  resultRef.current = result
  const captureRef = useRef<(() => string | null) | null>(null)
  const resaveTimer = useRef<number | null>(null)
  // Guards a create-save in flight so a re-render during the initial save can't spawn a duplicate.
  const creatingRef = useRef(false)
  // Set on reopen/restore so the model-ready that follows doesn't re-save unchanged saved work.
  const restoredRef = useRef(false)
  // UX-001: 'saving' is transient; 'saved' shows "Saved · My Designs"; 'error' self-heals via retry.
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const retryRef = useRef<number | null>(null)
  // Latest persist fn so the error-retry timer can re-invoke it without a self-referential closure.
  const persistRef = useRef<((opts?: { immediate?: boolean }) => Promise<void>) | null>(null)

  const applyResult = useCallback((r: DesignResponse | null) => {
    resultRef.current = r
    setResult(r)
  }, [])

  // --- save / persistence -------------------------------------------------
  const persist = useCallback(
    async (opts?: { immediate?: boolean }) => {
      const r = resultRef.current
      if (!r || !r.has_mesh) return
      const designId = designIdFromMeshUrl(r.mesh_url)
      if (designId == null) return
      const thumb = captureRef.current?.() ?? null
      const isCreate = !r.saved_id
      const run = async () => {
        if (isCreate && creatingRef.current) return
        if (isCreate) creatingRef.current = true
        setSaveState('saving')
        try {
          const saved = await saveDesign(designId, '', thumb, r.saved_id)
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

  const handleModelReady = useCallback(
    (capture: () => string | null) => {
      captureRef.current = capture
      if (restoredRef.current) {
        restoredRef.current = false
        return
      }
      void persist()
    },
    [persist],
  )

  // --- helpers -----------------------------------------------------------
  function resetSaveIndicator() {
    if (resaveTimer.current !== null) window.clearTimeout(resaveTimer.current)
    if (retryRef.current !== null) {
      window.clearTimeout(retryRef.current)
      retryRef.current = null
    }
    restoredRef.current = false
    setSaveState('idle')
  }

  /** Build the history list the backend needs from the current messages thread.
   *  We send only completed user+assistant pairs (not the in-progress user turn). */
  function buildHistory(): ChatTurn[] {
    return messages
      .filter((m): m is Message & { role: 'user' | 'assistant' } => m.role === 'user' || m.role === 'assistant')
      .map(({ role, content }) => ({ role, content }))
  }

  /** Run a design prompt (first turn or follow-up) and append the result to the thread.
   *  Pass history=undefined for a brand-new design, or the current thread for a refine turn. */
  async function runDesign(userPrompt: string, history?: ChatTurn[]) {
    setBusy(true)
    setError(null)
    try {
      const r = await postDesign(userPrompt, history)
      // Append the assistant reply as a message with appropriate tone.
      const tone = isFailureStatus(r.status) ? 'error' : undefined
      setMessages((prev) => [...prev, { role: 'assistant', content: assistantMessage(r), tone }])
      applyResult(r)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Something went wrong.'
      setMessages((prev) => [...prev, { role: 'assistant', content: msg, tone: 'error' }])
      setError(msg)
    } finally {
      setBusy(false)
    }
  }

  // --- design / refine / re-render ---------------------------------------
  async function handleSubmit(submitted: string) {
    resetSaveIndicator()
    navigate('', { replace: true })
    // Reset to a fresh conversation for a brand-new design.
    setMessages([{ role: 'user', content: submitted }])
    applyResult(null)
    setError(null)
    setRerenderError(null)
    setRerendering(false)
    renderSeq.current++
    await runDesign(submitted)
  }

  /** Follow-up: "make it 10mm taller", or answering a clarifying question.
   *  Threads the full prior conversation as history so the model has context. */
  async function handleRefine(followUp: string) {
    // Snapshot the current thread as history BEFORE appending the new user turn,
    // so the backend receives the prior conversation (not the turn being sent).
    const history = buildHistory()
    setMessages((prev) => [...prev, { role: 'user', content: followUp }])
    setError(null)
    setRerenderError(null)
    renderSeq.current++ // abandon any stale in-flight render
    await runDesign(followUp, history)
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
    setMessages([])
    applyResult(null)
    setError(null)
    setRerenderError(null)
    setRerendering(false)
    renderSeq.current++
    setBusy(false)
  }

  // Restore a saved design on a fresh page load at #/design/<id>.
  useEffect(() => {
    if (route.name !== 'design') return
    if (resultRef.current?.saved_id === route.id) return
    let cancelled = false
    renderSeq.current++
    setBusy(true)
    setError(null)
    setRerenderError(null)
    reopenDesign(route.id)
      .then((r) => {
        if (cancelled) return
        // Restore the single original prompt as the thread seed.
        setMessages([
          { role: 'user', content: r.prompt ?? '' },
          { role: 'assistant', content: assistantMessage(r) },
        ])
        applyResult(r)
        restoredRef.current = true
      })
      .catch(() => {
        if (!cancelled) setError("That design couldn't be opened.")
      })
      .finally(() => {
        if (!cancelled) setBusy(false)
      })
    return () => { cancelled = true }
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
            messages={messages}
            result={result}
            meshUrl={meshUrl}
            busy={busy}
            error={error}
            rerendering={rerendering}
            rerenderError={rerenderError}
            onRerender={handleRerender}
            onRefine={handleRefine}
            onModelReady={handleModelReady}
          />
        </Suspense>
      )}
    </div>
  )
}
