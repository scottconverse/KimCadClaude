import type { DesignResponse, DesignVersion, Message } from '../api'
import ChatPanel from './ChatPanel'
import RightPanel from './RightPanel'
import VersionRail from './VersionRail'
import Viewport from './Viewport'

// The three-column working view (conversation · viewport · parameters/printability).
// Stage 8.5 Slice 2: the left column renders the full message thread + refine input.
// The VersionRail appears above the workspace when the session has 2+ versions, giving
// the user one-click access to any prior design and an undo button.
export default function Workspace({
  messages,
  versions,
  versionIdx,
  result,
  meshUrl,
  busy,
  error,
  rerendering,
  rerenderError,
  onRerender,
  onRefine,
  onSwitchVersion,
  onModelReady,
}: {
  messages: Message[]
  versions: DesignVersion[]
  versionIdx: number
  result: DesignResponse | null
  meshUrl: string | null
  busy: boolean
  error: string | null
  rerendering: boolean
  rerenderError: string | null
  onRerender: (values: Record<string, number>) => void
  onRefine: (text: string) => void
  onSwitchVersion: (idx: number) => void
  onModelReady?: (capture: () => string | null) => void
}) {
  return (
    <div className="kc-workspace-wrap">
      <VersionRail versions={versions} versionIdx={versionIdx} onSwitch={onSwitchVersion} />
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
    </div>
  )
}
