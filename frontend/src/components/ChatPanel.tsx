import { useEffect, useRef, useState } from 'react'
import type { CompareMessage, DesignResponse, Message } from '../api'
import { gateLabel, gateTone } from '../designStatus'
import { useUnits } from '../useUnits'
import PhotoOnramp from './PhotoOnramp'

// Left column — the design conversation thread.
// Stage 8.5 Slice 2: renders all turns (user + assistant) as a scrollable thread, plus a
// "Refine your part" input so the user can follow up without leaving the workspace.
// A clarifying question from the model is just another assistant turn — the user types their
// answer in the refine input and the conversation continues in context.
function CubeGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2 21 7v10l-9 5-9-5V7Z" />
      <path d="M3 7l9 5 9-5" />
      <path d="M12 12v10" />
    </svg>
  )
}

// Axis labels for the bbox delta (target_bbox_mm is [width, depth, height]).
const BBOX_AXES = ['W', 'D', 'H']

/** Build the "what changed" lines between two versions: any bbox axis that moved (in the active
 *  display unit) plus a readiness-score delta. Empty when the two versions are dimensionally identical. */
function diffVersions(
  a: CompareMessage['a'],
  b: CompareMessage['b'],
  formatMm: (mm: number) => string,
  unit: string,
): string[] {
  const lines: string[] = []
  const bboxA = a.result.plan?.target_bbox_mm
  const bboxB = b.result.plan?.target_bbox_mm
  if (bboxA && bboxB && bboxA.length === bboxB.length) {
    bboxA.forEach((av, i) => {
      const bv = bboxB[i]
      if (typeof bv === 'number' && Math.abs(av - bv) > 0.01) {
        lines.push(`${BBOX_AXES[i] ?? `axis ${i + 1}`} ${formatMm(av)} → ${formatMm(bv)} ${unit}`)
      }
    })
  }
  const scoreA = a.result.report?.readiness?.score
  const scoreB = b.result.report?.readiness?.score
  if (scoreA != null && scoreB != null && scoreA !== scoreB) {
    lines.push(`Readiness ${scoreA} → ${scoreB}`)
  }
  return lines
}

function CompareCard({ card }: { card: CompareMessage }) {
  const { a, b } = card
  const { unit, formatMm } = useUnits()
  const sumA = a.result.plan?.summary ?? `v${a.index}`
  const sumB = b.result.plan?.summary ?? `v${b.index}`
  const gateA = a.result.report?.gate_status
  const gateB = b.result.report?.gate_status
  const scoreA = a.result.report?.readiness?.score
  const scoreB = b.result.report?.readiness?.score
  // UX-006: a "Compare" that only restates two summaries makes the user do the diffing. Surface
  // the actual delta so the card answers "what changed / which do I keep?".
  const changes = diffVersions(a, b, formatMm, unit)
  return (
    <div className="kc-compare-card" aria-label={`Comparing v${a.index} and v${b.index}`}>
      <div className="kc-compare-header">
        <span className="kc-compare-title">Comparing v{a.index} → v{b.index}</span>
      </div>
      <div className="kc-compare-cols">
        <div className="kc-compare-col">
          <div className="kc-compare-col-head">v{a.index}</div>
          <p className="kc-compare-sum">{sumA}</p>
          {/* UX-003: use the same gate vocabulary as the Printability card ("Passed", not "pass"). */}
          {gateA && <span className={`kc-compare-gate kc-gate-${gateTone(gateA)}`}>{gateLabel(gateA)}</span>}
          {scoreA != null && <span className="kc-compare-score">Readiness {scoreA}/100</span>}
        </div>
        <div className="kc-compare-divider" aria-hidden="true" />
        <div className="kc-compare-col">
          <div className="kc-compare-col-head">v{b.index}</div>
          <p className="kc-compare-sum">{sumB}</p>
          {gateB && <span className={`kc-compare-gate kc-gate-${gateTone(gateB)}`}>{gateLabel(gateB)}</span>}
          {scoreB != null && <span className="kc-compare-score">Readiness {scoreB}/100</span>}
        </div>
      </div>
      <div className="kc-compare-delta">
        {changes.length > 0 ? (
          <>
            <span className="kc-compare-delta-label">What changed</span>
            <ul className="kc-compare-delta-list">
              {changes.map((c) => <li key={c}>{c}</li>)}
            </ul>
          </>
        ) : (
          <span className="kc-compare-delta-none">No dimensional change between these versions.</span>
        )}
      </div>
    </div>
  )
}

export default function ChatPanel({
  messages,
  compareCard,
  result,
  busy,
  restoring,
  error,
  onRefine,
  onTryExperimental,
  onPhotoSeed,
  onRetry,
}: {
  messages: Message[]
  compareCard: CompareMessage | null
  result: DesignResponse | null
  busy: boolean
  restoring?: boolean
  error: string | null
  onRefine: (text: string) => void
  onTryExperimental: () => void
  onPhotoSeed: (seed: string) => void
  onRetry?: () => void
}) {
  const [draft, setDraft] = useState('')
  const bodyRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to the bottom whenever the thread grows.
  useEffect(() => {
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, busy])

  // Whether to show the refine input: we have a completed design (or a clarification question)
  // and the model isn't currently working.
  const hasResult = result !== null || (messages.length > 0 && !busy)
  const canRefine = hasResult && !busy

  function submit() {
    const text = draft.trim()
    if (!text) return
    setDraft('')
    onRefine(text)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const hasConversation = messages.length > 0 || busy || error !== null

  return (
    <aside className="kc-col-left">
      <div className="kc-panel-head">
        <span className="kc-eyebrow">Conversation</span>
      </div>

      <div className="kc-chat-body" ref={bodyRef} role="log" aria-live="polite" aria-busy={busy}>
        {!hasConversation && (
          <p className="kc-muted-note">
            Your design conversation will appear here as you refine the part.
          </p>
        )}

        {/* Render every turn in the thread */}
        {messages.map((msg, i) =>
          msg.role === 'user' ? (
            <div key={i} className="kc-msg kc-msg-user">{msg.content}</div>
          ) : (
            <div key={i} className="kc-ai-row">
              <span className="kc-ava" aria-hidden="true"><CubeGlyph /></span>
              <div className={`kc-msg kc-msg-ai${msg.tone === 'error' ? ' kc-msg-error' : ''}`}>
                {msg.content}
              </div>
            </div>
          )
        )}

        {/* Thinking indicator while a request is in flight. UX-008: during a FIRST design / reopen
            (no part on screen yet) the viewport's full overlay owns the progress — showing the same
            "Designing…" here too is a redundant duplicate. So only show this row for an in-thread
            REFINE (a part is already framed in the viewport), where it's the progress cue. */}
        {/* UX-007 (2026-06-09 audit): the thinking row is INSIDE the polite log, so each busy
            re-render would re-announce it on top of long assistant turns. aria-hidden takes it
            out of the live stream; the overlay's role=status (Viewport) already announces the
            run state once. Fuller live-region scoping is deferred until a real NVDA/VoiceOver
            session can measure it — changing log semantics blind risks making SR worse. */}
        {busy && result !== null && (
          <div className="kc-ai-row" aria-hidden="true">
            <span className="kc-ava"><CubeGlyph /></span>
            <div className="kc-think">
              <span className="kc-spin" />
              <span>{restoring ? 'Reopening your design…' : 'Refining your part…'}</span>
            </div>
          </div>
        )}

        {/* Slice 6 MS-4: the experimental-generator offer (no template fit). Never auto-run — the
            user explicitly opts in here, or re-describes the part in the refine input below. */}
        {!busy && result?.status === 'needs_experimental' && (
          <div className="kc-ai-row">
            <span className="kc-ava" aria-hidden="true"><CubeGlyph /></span>
            <div className="kc-exp-offer">
              <p className="kc-exp-warn">
                <b>Experimental · may not be perfect.</b> It runs in a locked sandbox and still has to
                pass the printability check — you’ll see exactly what happens. It writes the design on
                your computer’s AI, so it can take a few minutes; you can cancel anytime.
              </p>
              <button type="button" className="kc-btn kc-btn-accent kc-exp-try" onClick={onTryExperimental}>
                Try the experimental generator
              </button>
              <p className="kc-exp-decline">Or describe it differently below.</p>
            </div>
          </div>
        )}

        {/* Slice 9 MS-1: the model-down wall. The thread already shows the recoverable message;
            this adds a one-click "Try again" (re-runs the same attempt) so recovery isn't a retype. */}
        {!busy && result?.status === 'model_unavailable' && onRetry && (
          <div className="kc-ai-row">
            <span className="kc-ava" aria-hidden="true"><CubeGlyph /></span>
            <div className="kc-exp-offer">
              <button type="button" className="kc-btn kc-btn-accent kc-exp-try" onClick={onRetry}>
                Try again
              </button>
              <p className="kc-exp-decline">Start Ollama first — see the AI’s status in Settings.</p>
            </div>
          </div>
        )}

        {/* Compare card — injected when the user clicks Compare in the VersionRail */}
        {compareCard && <CompareCard card={compareCard} />}

        {/* Top-level network error (not a pipeline failure — those go into the thread) */}
        {!busy && error !== null && messages.every(m => m.content !== error) && (
          <div className="kc-ai-row">
            <span className="kc-ava" aria-hidden="true"><CubeGlyph /></span>
            <div className="kc-msg kc-msg-ai kc-msg-error">{error}</div>
          </div>
        )}
      </div>

      {/* Refine input — appears once there's a design to refine (or a clarification to answer) */}
      {canRefine && (
        <div className="kc-refine-wrap">
          {/* UX-003 / UX-010: one-tap refine chips + a persistent hint, so refine-by-talking isn't a
              blank box the user has to guess at. Hidden when the model is asking a clarifying
              question (the user must answer that, not request a generic change). Each chip threads a
              change through the same onRefine path as a typed message. */}
          {result?.status !== 'clarification_needed' && (
            <>
              <span className="kc-refine-hint">Refine by talking — tap a change or describe your own:</span>
              {/* UX-013 (2026-06-09 audit): chips are UNIVERSAL edits — size and walls apply to
                  every part family; the old "Add mounting holes" was a no-op for hole-less
                  shapes (a flat clip) and is better typed when it genuinely applies.
                  UX-110 (stage-BCD gate): grow/shrink offered symmetrically. */}
              <div className="kc-refine-chips" role="group" aria-label="Quick refinements">
                {['Make it bigger', 'Make it smaller', 'Make it taller', 'Thicker walls'].map(
                  (chip) => (
                    <button
                      key={chip}
                      type="button"
                      className="kc-chip kc-refine-chip"
                      onClick={() => onRefine(chip)}
                    >
                      {chip}
                    </button>
                  ),
                )}
              </div>
            </>
          )}
          <textarea
            ref={inputRef}
            className="kc-refine-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              result?.status === 'clarification_needed'
                ? 'Answer the question above…'
                : 'Refine your part — "make it 10mm taller", "add mounting holes"…'
            }
            aria-label="Refine your part"
            rows={2}
          />
          <button
            type="button"
            className="kc-btn kc-btn-accent kc-refine-send"
            onClick={submit}
            disabled={!draft.trim()}
            aria-label="Send refinement"
          >
            Send
          </button>
          {/* UX-006 (2026-06-09 audit): the keyboard contract, stated — a multi-line author
              shouldn't discover Enter-sends by accidentally firing a half-written request. */}
          <span className="kc-key-hint">Enter to send · Shift+Enter for a new line</span>
          {/* Slice 7: start a fresh part from a photo (a rough local-vision seed). Secondary to the
              refine input; using it begins a new design from the seed. */}
          <PhotoOnramp onSeed={onPhotoSeed} disabled={busy} variant="workspace" />
        </div>
      )}
    </aside>
  )
}
