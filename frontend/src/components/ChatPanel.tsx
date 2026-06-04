import { useEffect, useRef, useState } from 'react'
import type { DesignResponse, Message } from '../api'

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

export default function ChatPanel({
  messages,
  result,
  busy,
  error,
  onRefine,
}: {
  messages: Message[]
  result: DesignResponse | null
  busy: boolean
  error: string | null
  onRefine: (text: string) => void
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

        {/* Thinking indicator while a request is in flight */}
        {busy && (
          <div className="kc-ai-row">
            <span className="kc-ava" aria-hidden="true"><CubeGlyph /></span>
            <div className="kc-think">
              <span className="kc-spin" aria-hidden="true" />
              <span>Designing your part…</span>
            </div>
          </div>
        )}

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
        </div>
      )}
    </aside>
  )
}
