import { useState, type FormEvent } from 'react'

// The landing (empty) screen. Wired in Slice 3: the textarea + "Design it" submit a prompt,
// and clicking an example submits it directly. The photo on-ramp is a later stage and is
// intentionally absent.
const EXAMPLES = [
  'a wall-mounted holder for a 1 kg filament spool',
  'a 40 mm desk cable clip',
  'a hexagonal pen and tool organizer',
]

function SendGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12h13" />
      <path d="m13 6 6 6-6 6" />
    </svg>
  )
}

export default function Landing({
  onSubmit,
  busy,
}: {
  onSubmit: (prompt: string) => void
  busy: boolean
}) {
  const [value, setValue] = useState('')

  function submit(e: FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (trimmed && !busy) onSubmit(trimmed)
  }

  return (
    <main className="kc-landing">
      <div className="kc-landing-inner">
        <span className="kc-badge">
          <span className="kc-badge-dot" aria-hidden="true" />
          No CAD skills needed · runs entirely on your machine
        </span>
        <h1 className="kc-hero-title">What do you want to make today?</h1>
        <p className="kc-hero-sub">
          Describe a functional part in plain words — I&rsquo;ll design it, check that it&rsquo;s
          actually printable, and get it ready for your printer.
        </p>

        <form className="kc-input-card" onSubmit={submit}>
          <textarea
            className="kc-input"
            rows={2}
            placeholder="e.g. a wall-mounted holder for a 1 kg filament spool"
            aria-label="Describe the part you want"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            disabled={busy}
          />
          <button
            type="submit"
            className="kc-btn kc-btn-accent kc-design-btn"
            disabled={busy || value.trim() === ''}
          >
            Design it
            <SendGlyph />
          </button>
        </form>

        <div className="kc-examples">
          <span className="kc-examples-label">Try</span>
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="kc-chip"
              disabled={busy}
              onClick={() => onSubmit(example)}
            >
              {example}
            </button>
          ))}
        </div>

        <p className="kc-steps">
          <span>1. Describe</span>
          <span>2. Preview &amp; refine</span>
          <span>3. Check &amp; download</span>
        </p>
      </div>
    </main>
  )
}
