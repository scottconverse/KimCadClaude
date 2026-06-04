import type { DesignResponse, Message } from '../api'
import ChatPanel from './ChatPanel'
import RightPanel from './RightPanel'
import Viewport from './Viewport'

// The three-column working view (conversation · viewport · parameters/printability).
// Stage 8.5 Slice 2: the left column now receives the full message thread and an onRefine
// callback so the user can follow up ("make it 10mm taller") without leaving the workspace.
export default function Workspace({
  messages,
  result,
  meshUrl,
  busy,
  error,
  rerendering,
  rerenderError,
  onRerender,
  onRefine,
  onModelReady,
}: {
  messages: Message[]
  result: DesignResponse | null
  meshUrl: string | null
  busy: boolean
  error: string | null
  rerendering: boolean
  rerenderError: string | null
  onRerender: (values: Record<string, number>) => void
  onRefine: (text: string) => void
  onModelReady?: (capture: () => string | null) => void
}) {
  return (
    <div className="kc-workspace">
      <ChatPanel
        messages={messages}
        result={result}
        busy={busy}
        error={error}
        onRefine={onRefine}
      />
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
