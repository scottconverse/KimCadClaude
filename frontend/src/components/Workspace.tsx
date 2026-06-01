import ChatPanel from './ChatPanel'
import RightPanel from './RightPanel'
import Viewport from './Viewport'

// The three-column working view (conversation · viewport · parameters/printability). Stage 4,
// Slice 3 stands up the layout and the live viewport; the side panels fill in over Slices 4–5.
export default function Workspace({
  meshUrl,
  busy,
  notice,
}: {
  meshUrl: string | null
  busy: boolean
  notice: string | null
}) {
  return (
    <div className="kc-workspace">
      <ChatPanel notice={notice} />
      <Viewport meshUrl={meshUrl} busy={busy} />
      <RightPanel />
    </div>
  )
}
