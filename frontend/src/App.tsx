import { lazy, Suspense, useState } from 'react'
import Topbar from './components/Topbar'
import Landing from './components/Landing'
import { postDesign } from './api'

// The workspace pulls in three.js (the viewport). Code-split it so the landing screen loads
// without the 3D bundle; three is fetched the first time a part is designed.
const Workspace = lazy(() => import('./components/Workspace'))

// KimCad SPA — application shell + the minimal design flow.
//
// Stage 4, Slice 3: landing → describe → the real rendered mesh appears in the Three.js
// viewport. This wires only the mesh path (enough to prove real mesh loading); the rich
// conversation, plan summary, printability report, clarification/error UX, and the full set of
// PipelineStatus handling are filled in by Slice 4. Live sliders are Stage 5.
export default function App() {
  const [view, setView] = useState<'landing' | 'workspace'>('landing')
  const [meshUrl, setMeshUrl] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  async function handleSubmit(prompt: string) {
    setView('workspace')
    setMeshUrl(null)
    setNotice(null)
    setBusy(true)
    try {
      const result = await postDesign(prompt)
      if (result.has_mesh && result.mesh_url) {
        setMeshUrl(result.mesh_url)
      } else {
        setNotice(
          result.clarification ||
            result.error ||
            'KimCad couldn’t produce a preview for that request yet.',
        )
      }
    } catch (err) {
      setNotice(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  function handleNewDesign() {
    setView('landing')
    setMeshUrl(null)
    setNotice(null)
    setBusy(false)
  }

  return (
    <div className="kc-shell">
      <Topbar showNewDesign={view === 'workspace'} onNewDesign={handleNewDesign} />
      {view === 'landing' ? (
        <Landing onSubmit={handleSubmit} busy={busy} />
      ) : (
        <Suspense fallback={<div className="kc-workspace-loading">Loading workspace…</div>}>
          <Workspace meshUrl={meshUrl} busy={busy} notice={notice} />
        </Suspense>
      )}
    </div>
  )
}
