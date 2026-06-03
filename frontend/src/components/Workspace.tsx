import type { DesignResponse } from '../api'
import ChatPanel from './ChatPanel'
import RightPanel from './RightPanel'
import Viewport from './Viewport'

// The three-column working view (conversation · viewport · parameters/printability), wired to
// the design result in Slice 4. The right column owns the live parameter sliders (Stage 5): a
// drag debounces a deterministic re-render via `onRerender`, and `rerendering` keeps the last
// mesh on screen with a quiet "Updating…" while the new geometry lands.
export default function Workspace({
  prompt,
  result,
  meshUrl,
  busy,
  error,
  rerendering,
  rerenderError,
  onRerender,
  onModelReady,
}: {
  prompt: string
  result: DesignResponse | null
  meshUrl: string | null
  busy: boolean
  error: string | null
  rerendering: boolean
  rerenderError: string | null
  onRerender: (values: Record<string, number>) => void
  onModelReady?: (capture: () => string | null) => void
}) {
  return (
    <div className="kc-workspace">
      <ChatPanel prompt={prompt} result={result} busy={busy} error={error} />
      <Viewport meshUrl={meshUrl} busy={busy} onModelReady={onModelReady} />
      <RightPanel
        result={result}
        rerendering={rerendering}
        rerenderError={rerenderError}
        onRerender={onRerender}
      />
    </div>
  )
}
