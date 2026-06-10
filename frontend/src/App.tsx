import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import {
  designIdFromMeshUrl,
  getDesignProgress,
  isAbortError,
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
import FirstRunWizard from './components/FirstRunWizard'
import Landing from './components/Landing'
import MyDesigns from './components/MyDesigns'
import SettingsPanel from './components/SettingsPanel'
import ShortcutsHelp from './components/ShortcutsHelp'
import Topbar from './components/Topbar'
import { useHashRoute } from './useHashRoute'

// The workspace pulls in three.js (the viewport). Code-split it so the landing screen loads
// without the 3D bundle; three is fetched the first time a part is designed.
const Workspace = lazy(() => import('./components/Workspace'))

// MS-3: a short, URL-safe id for one design run so the UI can poll its progress. Matches the
// server's job-id rule ([A-Za-z0-9-]{1,64}): crypto.randomUUID where available, else a random token.
function makeJobId(): string {
  const c = globalThis.crypto as Crypto | undefined
  if (c?.randomUUID) return c.randomUUID()
  return `job-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

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
  // Lets the user cancel an in-flight design (the local model can run for minutes) and escape the
  // "Designing your part…" screen. The elapsed seconds tick a live counter so it never looks frozen.
  const designAbortRef = useRef<AbortController | null>(null)
  const busyStartRef = useRef<number>(0)
  // Monotonic guard so a superseded design (cancelled, or replaced by a New Design / new submit
  // while it was still in flight) can't apply its late result into a fresh session — the design
  // analogue of `renderSeq` below.
  const designSeqRef = useRef(0)
  const [designElapsed, setDesignElapsed] = useState(0)
  // MS-3: the current run's phase (planning/generating/rendering/validating), polled from the
  // server while busy so the "Designing…" screen shows WHAT it's doing, not just elapsed time.
  const [designPhase, setDesignPhase] = useState<string | null>(null)
  const designJobRef = useRef<string | null>(null)
  // `busy` covers both a model design run AND reopening a saved design. Only the former is a
  // cancelable, elapsed-timed model call — so the busy overlay must know which it is (ENG-001/002:
  // a reopen was showing the "Designing…" overlay with a garbage timer and a dead Cancel).
  const [restoring, setRestoring] = useState(false)
  // MS-4: the first-run setup wizard shows until the user finishes or skips it (a persisted flag).
  // Read once on mount; localStorage is the right home for a per-install "have we onboarded" bit
  // (the actual choices — printer, cloud — persist server-side via the settings endpoints).
  const [showWizard, setShowWizard] = useState(() => {
    try {
      return localStorage.getItem('kc-first-run-done') !== '1'
    } catch {
      return false
    }
  })
  const dismissWizard = useCallback(() => {
    try {
      localStorage.setItem('kc-first-run-done', '1')
    } catch {
      /* a private-mode storage failure just means the wizard may show again next time — harmless. */
    }
    setShowWizard(false)
  }, [])
  // Slice 11: the keyboard-shortcuts help overlay (opened with "?").
  const [showShortcuts, setShowShortcuts] = useState(false)
  // Latest shortcut actions, so the global keydown listener calls current handlers without
  // re-binding on every render (handlers close over fresh state each render).
  const shortcutsRef = useRef<{ newDesign: () => void; goDesigns: () => void; goSettings: () => void }>({
    newDesign: () => {},
    goDesigns: () => {},
    goSettings: () => {},
  })
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

  // While a design is running, tick an elapsed-seconds counter (~2 Hz) so the "Designing…" screen
  // shows live progress rather than a frozen spinner. Reset to 0 when the run ends.
  useEffect(() => {
    if (!busy) {
      setDesignElapsed(0)
      return
    }
    const tick = () => setDesignElapsed(Math.max(0, Math.round((Date.now() - busyStartRef.current) / 1000)))
    tick()
    const id = window.setInterval(tick, 500)
    return () => window.clearInterval(id)
  }, [busy])

  // MS-3: while a real design run is in flight (not a reopen), poll its phase (~1.2 s) so the
  // "Designing…" screen shows a live step — planning → generating → rendering → validating —
  // instead of only an elapsed timer. The phase resets to null whenever a run isn't active.
  useEffect(() => {
    if (!busy || restoring) {
      setDesignPhase(null)
      return
    }
    let stopped = false
    const poll = async () => {
      const jobId = designJobRef.current
      if (!jobId) return
      const { phase } = await getDesignProgress(jobId)
      if (!stopped) setDesignPhase(phase)
    }
    void poll()
    const id = window.setInterval(poll, 1200)
    return () => {
      stopped = true
      window.clearInterval(id)
    }
  }, [busy, restoring])

  // Escape key cancels an in-flight design too — a keyboard escape from the "Designing…" screen.
  // But when the shortcuts help is open, Esc belongs to the help (close it first), not the design —
  // otherwise dismissing the overlay would also abort the run underneath it.
  useEffect(() => {
    if (!busy) return
    const onKey = (e: KeyboardEvent) => {
      if (showShortcuts) return
      if (e.key === 'Escape') designAbortRef.current?.abort()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, showShortcuts])

  // Slice 11: global keyboard shortcuts. Bare-key shortcuts fire ONLY when the user isn't typing in
  // a field and no modifier is held, so browser/OS combos (Ctrl/Cmd+N, etc.) pass straight through.
  // "?" toggles the shortcuts help; n/d/, navigate; Esc closes the help (design-cancel Esc is above).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return
      const t = e.target as HTMLElement | null
      // Don't hijack keys while the user is typing. `isContentEditable` is the right semantic in a
      // real browser; the attribute check is the fallback (and what jsdom understands in tests).
      const ce = t?.getAttribute?.('contenteditable')
      if (
        t &&
        (t.tagName === 'INPUT' ||
          t.tagName === 'TEXTAREA' ||
          t.tagName === 'SELECT' ||
          t.isContentEditable ||
          (ce != null && ce !== 'false'))
      )
        return
      if (showWizard) return // the wizard owns the keyboard while it's open
      if (e.key === '?') {
        e.preventDefault()
        setShowShortcuts((s) => !s)
        return
      }
      if (showShortcuts) {
        if (e.key === 'Escape') setShowShortcuts(false)
        return // while the help is open, don't also trigger navigation
      }
      const a = shortcutsRef.current
      if (e.key === 'n' || e.key === 'N') {
        e.preventDefault()
        a.newDesign()
      } else if (e.key === 'd' || e.key === 'D') {
        e.preventDefault()
        a.goDesigns()
      } else if (e.key === ',') {
        e.preventDefault()
        a.goSettings()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [showWizard, showShortcuts])

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
    const seq = ++designSeqRef.current
    // Supersede any still-in-flight design so its late resolve can't pollute this run.
    designAbortRef.current?.abort()
    const controller = new AbortController()
    designAbortRef.current = controller
    // MS-3: a fresh job id for this run's progress poll; clear any stale phase from a prior run.
    const jobId = makeJobId()
    designJobRef.current = jobId
    setDesignPhase(null)
    busyStartRef.current = Date.now()
    setRestoring(false) // this is a real model design run, not a reopen
    setBusy(true)
    setError(null)
    try {
      const r = await postDesign(userPrompt, history, experimental, controller.signal, jobId)
      if (seq !== designSeqRef.current) return // a newer design replaced this one — drop the result
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
      if (seq !== designSeqRef.current) return // superseded (incl. our own abort on replace) — ignore
      if (isAbortError(err)) {
        // The user cancelled — return quietly. Only worth a thread note if they stay in the
        // workspace (a refine); a first-design cancel returns to the landing, where it'd be unseen.
        if (resultRef.current) {
          setMessages((prev) => [...prev, { role: 'assistant', content: 'Cancelled — back to you.' }])
        }
      } else {
        const msg = err instanceof Error ? err.message : 'Something went wrong.'
        setMessages((prev) => [...prev, { role: 'assistant', content: msg, tone: 'error' }])
        setError(msg)
      }
    } finally {
      // Clear the progress job only if it's still ours (a newer run already replaced it otherwise).
      if (designJobRef.current === jobId) designJobRef.current = null
      if (seq === designSeqRef.current) {
        if (designAbortRef.current === controller) designAbortRef.current = null
        setBusy(false)
      }
    }
  }

  /** Cancel an in-flight design and escape the "Designing your part…" screen. Aborts the request so
   *  the UI returns to the prompt immediately (the local model may finish its current pass in the
   *  background, but the user is no longer stuck waiting on it). */
  function handleCancelDesign() {
    designAbortRef.current?.abort()
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

  /** Retry the last design attempt unchanged — the model-down wall's "Try again" (start Ollama,
   *  then retry). Re-runs the same prompt/history; no new user turn. */
  async function handleRetry() {
    const a = lastAttemptRef.current
    if (!a) return
    setError(null)
    setRerenderError(null)
    renderSeq.current++
    await runDesign(a.prompt, a.history, a.fromVersionIdx)
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
    // Supersede + abort any in-flight design so a late resolve can't repopulate this fresh slate.
    designSeqRef.current++
    designAbortRef.current?.abort()
    designAbortRef.current = null
    setRestoring(false)
    setBusy(false)
  }

  // Keep the shortcut actions current for the global keydown listener (declared once, above).
  shortcutsRef.current = {
    newDesign: handleNewDesign,
    goDesigns: () => navigate('designs'),
    goSettings: () => navigate('settings'),
  }

  // Restore a saved design on a fresh page load at #/design/<id>.
  useEffect(() => {
    if (route.name !== 'design') return
    if (resultRef.current?.saved_id === route.id) return
    let cancelled = false
    renderSeq.current++
    setRestoring(true) // a reopen, not a design run — the overlay shows "Reopening…", no timer/Cancel
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
        if (!cancelled) {
          setRestoring(false)
          setBusy(false)
        }
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
      <a className="kc-skip-link" href="#kimcad-main">
        Skip to main content
      </a>
      {showWizard && <FirstRunWizard onClose={dismissWizard} />}
      {showShortcuts && <ShortcutsHelp onClose={() => setShowShortcuts(false)} />}
      <Topbar
        showNewDesign={onWorkspace}
        onNewDesign={handleNewDesign}
        onMyDesigns={() => navigate('designs')}
        onSettings={() => navigate('settings')}
        onShowShortcuts={() => setShowShortcuts(true)}
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
            restoring={restoring}
            busyElapsed={designElapsed}
            busyPhase={designPhase}
            onCancelDesign={handleCancelDesign}
            error={error}
            rerendering={rerendering}
            rerenderError={rerenderError}
            onRerender={handleRerender}
            onRefine={handleRefine}
            onSwitchVersion={handleSwitchVersion}
            onCompare={handleCompare}
            onTryExperimental={handleTryExperimental}
            onPhotoSeed={handleSubmit}
            onRetry={handleRetry}
            onModelReady={handleModelReady}
          />
        </Suspense>
      )}
    </div>
  )
}
