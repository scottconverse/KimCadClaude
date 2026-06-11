import { useEffect, useMemo, useState } from 'react'
import type { CompareMessage, DesignResponse, DesignVersion, Message } from '../api'
import type { HighlightRisk } from '../viewport/KCViewport'
import ChatPanel from './ChatPanel'
import RightPanel, { type InspectorTab } from './RightPanel'
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

  // UI-v2 slice 2 (#23): the Inspector's active tab, lifted here so the mobile CTA (and the
  // viewport's risk-focus) can drive it. Smart default per GEOMETRY OUTCOME: a part that
  // fails the gate opens on Quality (you need to see why — including a slider drag that
  // newly fails); a passing part opens on Parameters (the sliders are the hero).
  const [tab, setTab] = useState<InspectorTab>('parameters')
  const gateKey = result?.report ? `${result.mesh_url ?? ''}:${result.report.gate_status}` : null
  useEffect(() => {
    if (!gateKey) return
    setTab(gateKey.endsWith(':fail') ? 'quality' : 'parameters')
  }, [gateKey])
  // Clicking a readiness risk must land the user back on Quality when they return from the
  // viewport — keep the tab and the focus action together.
  const focusRiskOnQuality = (id: string) => {
    setTab('quality')
    focusRisk(id)
  }

  return (
    <main id="kimcad-main" className="kc-workspace-wrap">
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
          onFocusRisk={focusRiskOnQuality}
          highlightsOn={highlightsOn}
          onToggleHighlights={() => setHighlightsOn((v) => !v)}
          tab={tab}
          onTab={setTab}
        />
      </div>
      {/* UX-004: on a phone the readiness verdict + Slice/Download sit below a tall viewport, off the
          fold. A mobile-only sticky bar jumps straight to those print actions — switching the
          Inspector to the Export tab first (slice 2), else the target card is hidden. */}
      {result?.has_mesh && (
        <button
          type="button"
          className="kc-mobile-cta"
          onClick={() => {
            setTab('export')
            // Scroll after the tabpanel un-hides (next frame).
            requestAnimationFrame(() =>
              document
                .getElementById('kc-export-card')
                ?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
            )
          }}
        >
          ↓ Check &amp; download
        </button>
      )}
    </main>
  )
}
