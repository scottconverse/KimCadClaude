import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import {
  designIdFromMeshUrl,
  postDesign,
  postRender,
  reopenDesign,
  saveDesign,
  type ChatTurn,
  type CompareMessage,
  type DesignResponse,
  type DesignVersion,
  type Message,
} from './api'
import { assistantMessage, isFailureStatus } from './designStatus'
import Landing from './components/Landing'
import MyDesigns from './components/MyDesigns'
import SettingsPanel from './components/SettingsPanel'
import Topbar from './components/Topbar'
import { useHashRoute } from './useHashRoute'

// The workspace pulls in three.js (the viewport). Code-split it so the landing screen loads
// without the 3D bundle; three is fetched the first time a part is designed.
const Workspace = lazy(() => import('./components/Workspace'))

const RERENDER_MIN_DWELL_MS = 350
// QA-001: autosave coalescing window. Each settled re-render lands a new mesh and would otherwise
// trigger its own save; this debounce collapses a burst of slider/numeric edits into one save. Sized
// comfortably above a fast (loopback) re-render so an active editing session saves once when it
// settles, not on every nudge — and it stays robust when a slower real renderer lands.
const RESAVE_DEBOUNCE_MS = 1500

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
  // Version history: each successful design / refine push a snapshot. The user can step back.
  const [versions, setVersions] = useState<DesignVersion[]>([])
  // Which version is currently active (0-based index into versions, or -1 when no versions yet).
  const [versionIdx, setVersionIdx] = useState(-1)
  // A pending compare card (injected into the thread when the user clicks Compare).
  const [compareCard, setCompareCard] = useState<CompareMessage | null>(null)
  // The most recent completed design result — drives the viewport + right panel.
  const [result, setResult] = useState<DesignResponse | null>(null)
  const [busy, setBusy] = useState(false)
  // A top-level network/unexpected error (not a pipeline status failure — those surface as
  // assistant messages with error tone in the thread).
  const [error, setError] = useState<string | null>(null)
  const [rerendering, setRerendering] = useState(false)
  const [rerenderError, setRerenderError] = useState<string | null>(null)
  const renderSeq = useRef(0)
  // Slice 6 MS-4: the last design attempt, so the experimental-generator offer can re-run it.
  const lastAttemptRef = useRef<{ prompt: string; history?: ChatTurn[]; fromVersionIdx?: number } | null>(null)
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
   *  Pass history=undefined for a brand-new design, or the current thread for a refine turn.
   *  On success, pushes a new version entry so the user can step back. If the user refined from
   *  a prior version, future versions are truncated (branching replaces forward history). */
  async function runDesign(
    userPrompt: string,
    history?: ChatTurn[],
    fromVersionIdx?: number,
    experimental = false,
  ) {
    // Remember this attempt so the "try the experimental generator" offer can re-run it.
    lastAttemptRef.current = { prompt: userPrompt, history, fromVersionIdx }
    setBusy(true)
    setError(null)
    try {
      const r = await postDesign(userPrompt, history, experimental)
      const tone = isFailureStatus(r.status) ? 'error' : undefined
      const assistantMsg: Message = { role: 'assistant', content: assistantMessage(r), tone }
      setMessages((prev) => {
        const next = [...prev, assistantMsg]
        // Push a version snapshot if the result has a mesh (completed or gate_failed — still a
        // real part the user might want to revisit). Clarification_needed doesn't become a version.
        if (r.has_mesh) {
          setVersions((prevVers) => {
            // Branching: if the user refined from a prior version, drop any forward versions.
            const base = fromVersionIdx !== undefined ? prevVers.slice(0, fromVersionIdx + 1) : prevVers
            const newVer: DesignVersion = {
              index: base.length + 1,
              messages: next,
              result: r,
              label: userPrompt.length > 60 ? userPrompt.slice(0, 57) + '…' : userPrompt,
            }
            const updated = [...base, newVer]
            setVersionIdx(updated.length - 1)
            return updated
          })
        }
        return next
      })
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
    setMessages([{ role: 'user', content: submitted }])
    setVersions([])
    setVersionIdx(-1)
    setCompareCard(null)
    applyResult(null)
    setError(null)
    setRerenderError(null)
    setRerendering(false)
    renderSeq.current++
    await runDesign(submitted)
  }

  /** Follow-up: "make it 10mm taller", or answering a clarifying question.
   *  Threads the full prior conversation as history so the model has context.
   *  If the user branched from a prior version (versionIdx < last), forward versions are dropped. */
  async function handleRefine(followUp: string) {
    const history = buildHistory()
    // Pass the current versionIdx so runDesign knows whether to truncate forward versions.
    const fromIdx = versionIdx >= 0 ? versionIdx : undefined
    setMessages((prev) => [...prev, { role: 'user', content: followUp }])
    setError(null)
    setRerenderError(null)
    renderSeq.current++
    await runDesign(followUp, history, fromIdx)
  }

  /** The user accepted the experimental-generator offer — re-run the same attempt with codegen
   *  allowed (no new user turn; just appends the assistant's result). */
  async function handleTryExperimental() {
    const a = lastAttemptRef.current
    if (!a) return
    setError(null)
    setRerenderError(null)
    renderSeq.current++
    await runDesign(a.prompt, a.history, a.fromVersionIdx, true)
  }

  /** Show a comparison card between two versions (default: the two most recent). */
  function handleCompare(aIdx: number, bIdx: number) {
    const a = versions[aIdx]
    const b = versions[bIdx]
    if (!a || !b) return
    setCompareCard({ type: 'compare', a, b })
  }

  /** Step back/forward to a specific version. Restores the messages + result from that snapshot. */
  function handleSwitchVersion(idx: number) {
    const ver = versions[idx]
    if (!ver) return
    resetSaveIndicator() // clear any in-flight save indicator from the version being left
    setMessages(ver.messages)
    applyResult(ver.result)
    setVersionIdx(idx)
    setError(null)
    setRerenderError(null)
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
    setVersions([])
    setVersionIdx(-1)
    setCompareCard(null)
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
        const seedMsgs: Message[] = [
          { role: 'user', content: r.prompt ?? '' },
          { role: 'assistant', content: assistantMessage(r) },
        ]
        setMessages(seedMsgs)
        // Seed version history with the restored snapshot so the user can refine from v1.
        if (r.has_mesh) {
          const v1: DesignVersion = {
            index: 1, messages: seedMsgs, result: r,
            label: (r.prompt ?? '').slice(0, 60) || 'Original',
          }
          setVersions([v1])
          setVersionIdx(0)
        } else {
          setVersions([])
          setVersionIdx(-1)
        }
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
  const onWorkspace =
    route.name !== 'designs' &&
    route.name !== 'settings' &&
    (result !== null || busy || route.name === 'design')

  return (
    <div className="kc-shell">
      <Topbar
        showNewDesign={onWorkspace}
        onNewDesign={handleNewDesign}
        onMyDesigns={() => navigate('designs')}
        onSettings={() => navigate('settings')}
        onHome={handleNewDesign}
        activeRoute={route.name}
        saveState={saveState}
        savedId={result?.saved_id ?? null}
      />
      {route.name === 'designs' ? (
        <MyDesigns onOpen={(id) => navigate(`design/${id}`)} onNew={handleNewDesign} />
      ) : route.name === 'settings' ? (
        <SettingsPanel />
      ) : !onWorkspace ? (
        <Landing onSubmit={handleSubmit} busy={busy} />
      ) : (
        <Suspense fallback={<div className="kc-workspace-loading">Loading workspace…</div>}>
          <Workspace
            messages={messages}
            compareCard={compareCard}
            versions={versions}
            versionIdx={versionIdx}
            result={result}
            meshUrl={meshUrl}
            busy={busy}
            error={error}
            rerendering={rerendering}
            rerenderError={rerenderError}
            onRerender={handleRerender}
            onRefine={handleRefine}
            onSwitchVersion={handleSwitchVersion}
            onCompare={handleCompare}
            onTryExperimental={handleTryExperimental}
            onPhotoSeed={handleSubmit}
            onModelReady={handleModelReady}
          />
        </Suspense>
      )}
    </div>
  )
}
