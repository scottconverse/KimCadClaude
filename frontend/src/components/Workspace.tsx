import { useMemo, useState } from 'react'
import type { CompareMessage, DesignResponse, DesignVersion, Message } from '../api'
import type { HighlightRisk } from '../viewport/KCViewport'
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
  restoring,
  busyElapsed,
  busyPhase,
  onCancelDesign,
  error,
  rerendering,
  rerenderError,
  onRerender,
  onRefine,
  onSwitchVersion,
  onCompare,
  onTryExperimental,
  onPhotoSeed,
  onRetry,
  onModelReady,
}: {
  messages: Message[]
  compareCard: CompareMessage | null
  versions: DesignVersion[]
  versionIdx: number
  result: DesignResponse | null
  meshUrl: string | null
  busy: boolean
  restoring: boolean
  busyElapsed: number
  busyPhase?: string | null
  onCancelDesign: () => void
  error: string | null
  rerendering: boolean
  rerenderError: string | null
  onRerender: (values: Record<string, number>) => void
  onRefine: (text: string) => void
  onSwitchVersion: (idx: number) => void
  onCompare: (aIdx: number, bIdx: number) => void
  onTryExperimental: () => void
  onPhotoSeed: (seed: string) => void
  onRetry?: () => void
  onModelReady?: (capture: () => string | null) => void
}) {
  // Slice 8: problem highlights on the model. The risks with geometry (from PrintProof3D) are
  // shown on the part; clicking a located risk in the readiness card focuses it in the viewport.
  const [highlightsOn, setHighlightsOn] = useState(true)
  const [focus, setFocus] = useState<{ id: string; n: number } | null>(null)
  const highlights = useMemo<HighlightRisk[]>(() => {
    const risks = result?.report?.readiness?.risks ?? []
    return risks
      .filter((r) => r.geometry && r.issueId)
      .map((r) => ({ issueId: r.issueId as string, tone: r.tone, geometry: r.geometry! }))
  }, [result])
  // A nonce so clicking the same risk twice still re-focuses it.
  const focusRisk = (id: string) => {
    setHighlightsOn(true)
    setFocus((f) => ({ id, n: (f?.n ?? 0) + 1 }))
  }

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
          restoring={restoring}
          error={error}
          onRefine={onRefine}
          onTryExperimental={onTryExperimental}
          onPhotoSeed={onPhotoSeed}
          onRetry={onRetry}
        />
        <Viewport
          meshUrl={meshUrl}
          busy={busy}
          restoring={restoring}
          busyElapsed={busyElapsed}
          busyPhase={busyPhase}
          onCancelDesign={onCancelDesign}
          onModelReady={onModelReady}
          highlights={highlights}
          showHighlights={highlightsOn}
          focus={focus}
        />
        <RightPanel
          result={result}
          rerendering={rerendering}
          rerenderError={rerenderError}
          onRerender={onRerender}
          onFocusRisk={focusRisk}
          highlightsOn={highlightsOn}
          onToggleHighlights={() => setHighlightsOn((v) => !v)}
        />
      </div>
      {/* UX-004: on a phone the readiness verdict + Slice/Download sit below a tall viewport, off the
          fold. A mobile-only sticky bar jumps straight to those print actions. Hidden on desktop. */}
      {result?.has_mesh && (
        <button
          type="button"
          className="kc-mobile-cta"
          onClick={() =>
            document
              .getElementById('kc-export-card')
              ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }
        >
          ↓ Check &amp; download
        </button>
      )}
    </div>
  )
}
