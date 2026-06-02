import type { ReactNode } from 'react'
import type { DesignResponse } from '../api'
import { assistantMessage, isFailureStatus } from '../designStatus'

// Left column — the design conversation. Renders the user's prompt, a thinking state while the
// design runs, then the assistant's reply (clarifying question, built summary, or build error).
// Assistant rows carry a small cube avatar, matching the design.
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

function AssistantRow({ children, tone }: { children: ReactNode; tone?: 'error' }) {
  return (
    <div className="kc-ai-row">
      <span className="kc-ava" aria-hidden="true">
        <CubeGlyph />
      </span>
      <div className={`kc-msg kc-msg-ai${tone === 'error' ? ' kc-msg-error' : ''}`}>{children}</div>
    </div>
  )
}

export default function ChatPanel({
  prompt,
  result,
  busy,
  error,
}: {
  prompt: string
  result: DesignResponse | null
  busy: boolean
  error: string | null
}) {
  const hasConversation = prompt !== '' || busy || error !== null || result !== null
  return (
    <aside className="kc-col-left">
      <div className="kc-panel-head">
        <span className="kc-eyebrow">Conversation</span>
      </div>
      <div className="kc-chat-body" role="log" aria-live="polite" aria-busy={busy}>
        {!hasConversation && (
          <p className="kc-muted-note">
            Your design conversation will appear here as you refine the part.
          </p>
        )}
        {prompt !== '' && <div className="kc-msg kc-msg-user">{prompt}</div>}
        {busy && (
          <div className="kc-ai-row">
            <span className="kc-ava" aria-hidden="true">
              <CubeGlyph />
            </span>
            <div className="kc-think">
              <span className="kc-spin" aria-hidden="true" />
              <span>Designing your part…</span>
            </div>
          </div>
        )}
        {!busy && error !== null && <AssistantRow tone="error">{error}</AssistantRow>}
        {!busy && error === null && result !== null && (
          // A status-based failure (plan/render/gate) gets the error tone too, so the bubble
          // reads as a failure rather than sitting in the same neutral grey as a success.
          <AssistantRow tone={isFailureStatus(result.status) ? 'error' : undefined}>
            {assistantMessage(result)}
          </AssistantRow>
        )}
      </div>
    </aside>
  )
}
