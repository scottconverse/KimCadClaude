import type { DesignResponse } from '../api'
import ChatPanel from './ChatPanel'
import RightPanel from './RightPanel'
import Viewport from './Viewport'

// The three-column working view (conversation · viewport · parameters/printability), wired to
// the design result in Slice 4.
export default function Workspace({
  prompt,
  result,
  meshUrl,
  busy,
  error,
}: {
  prompt: string
  result: DesignResponse | null
  meshUrl: string | null
  busy: boolean
  error: string | null
}) {
  return (
    <div className="kc-workspace">
      <ChatPanel prompt={prompt} result={result} busy={busy} error={error} />
      <Viewport meshUrl={meshUrl} busy={busy} />
      <RightPanel result={result} />
    </div>
  )
}
