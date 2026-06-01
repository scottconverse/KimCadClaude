import { lazy, Suspense, useState } from 'react'
import Topbar from './components/Topbar'
import Landing from './components/Landing'
import { postDesign, type DesignResponse } from './api'

// The workspace pulls in three.js (the viewport). Code-split it so the landing screen loads
// without the 3D bundle; three is fetched the first time a part is designed.
const Workspace = lazy(() => import('./components/Workspace'))

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

  async function handleSubmit(submitted: string) {
    setView('workspace')
    setPrompt(submitted)
    setResult(null)
    setError(null)
    setBusy(true)
    try {
      setResult(await postDesign(submitted))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  function handleNewDesign() {
    setView('landing')
    setPrompt('')
    setResult(null)
    setError(null)
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
          />
        </Suspense>
      )}
    </div>
  )
}
