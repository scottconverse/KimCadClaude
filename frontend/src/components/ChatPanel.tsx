// Left column — the design conversation.
//
// Slice 3 is a static scaffold plus a slot for the one notice the minimal flow can produce (a
// clarifying question or an error from the design call). The full conversation — user/assistant
// bubbles, the thinking checklist, refine chips — is wired in Slice 4.
export default function ChatPanel({ notice }: { notice: string | null }) {
  return (
    <aside className="kc-col-left">
      <div className="kc-panel-head">
        <span className="kc-eyebrow">Conversation</span>
      </div>
      <div className="kc-chat-body">
        {notice ? (
          <p className="kc-chat-notice">{notice}</p>
        ) : (
          <p className="kc-muted-note">
            Your design conversation will appear here as you refine the part.
          </p>
        )}
      </div>
    </aside>
  )
}
