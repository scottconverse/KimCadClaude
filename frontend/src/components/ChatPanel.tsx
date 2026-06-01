import type { DesignResponse } from '../api'
import { assistantMessage } from '../designStatus'

// Left column — the design conversation. Slice 4 renders the real exchange: the user's prompt,
// a thinking state while the design runs, then the assistant's reply (a clarifying question, the
// built summary, or a build error) derived from the PipelineStatus. The full multi-turn refine
// flow + the parameter-history rail come later.
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
          <div className="kc-think">
            <span className="kc-spin" aria-hidden="true" />
            <span>Designing your part…</span>
          </div>
        )}
        {!busy && error !== null && (
          <div className="kc-msg kc-msg-ai kc-msg-error">{error}</div>
        )}
        {!busy && error === null && result !== null && (
          <div className="kc-msg kc-msg-ai">{assistantMessage(result)}</div>
        )}
      </div>
    </aside>
  )
}
