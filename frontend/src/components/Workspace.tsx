import type { CompareMessage, DesignResponse, DesignVersion, Message } from '../api'
import ChatPanel from './ChatPanel'
import RightPanel from './RightPanel'
import VersionRail from './VersionRail'
import Viewport from './Viewport'

export default function Workspace({
  messages,
  compareCard,
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
  onCompare,
  onModelReady,
}: {
  messages: Message[]
  compareCard: CompareMessage | null
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
  onCompare: (aIdx: number, bIdx: number) => void
  onModelReady?: (capture: () => string | null) => void
}) {
  return (
    <div className="kc-workspace-wrap">
      <VersionRail
        versions={versions}
        versionIdx={versionIdx}
        onSwitch={onSwitchVersion}
        onCompare={onCompare}
      />
      <div className="kc-workspace">
        <ChatPanel
          messages={messages}
          compareCard={compareCard}
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
