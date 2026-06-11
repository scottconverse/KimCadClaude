import { useState, type FormEvent, type KeyboardEvent } from 'react'
import ModelHealthPill from './ModelHealthPill'
import PhotoOnramp from './PhotoOnramp'

// The landing (empty) screen. Wired in Slice 3: the textarea + "Design it" submit a prompt,
// and clicking an example submits it directly. Stage 8.5 Slice 7 adds the "describe with a photo"
// on-ramp (Surface D) as a secondary affordance beside the text box — text stays the primary path.
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

// The capability strip below the fold — it conveys the whole product arc (three on-ramps →
// printability checking → slice/print → local-first) without crowding the prompt-first flow.
function CapGlyph({ name }: { name: 'ways' | 'check' | 'print' | 'local' }) {
  const common = {
    viewBox: '0 0 24 24', width: 22, height: 22, fill: 'none', stroke: 'currentColor',
    strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
  if (name === 'ways')
    return (
      <svg {...common}>
        <path d="M3 7h11M3 12h7M3 17h9" />
        <path d="M17 14.5 20.5 18 17 21.5" />
        <circle cx="18.5" cy="6.5" r="3" />
      </svg>
    )
  if (name === 'check')
    return (
      <svg {...common}>
        <path d="M12 3 5 6v6c0 4 3 6.5 7 9 4-2.5 7-5 7-9V6Z" />
        <path d="m9 12 2 2 4-4" />
      </svg>
    )
  if (name === 'print')
    return (
      <svg {...common}>
        <path d="M7 9V4h10v5" />
        <path d="M5 9h14a2 2 0 0 1 2 2v5h-4M5 16H3v-5a2 2 0 0 1 2-2Z" />
        <rect x="7" y="14" width="10" height="6" rx="1" />
      </svg>
    )
  return (
    <svg {...common}>
      <rect x="5" y="11" width="14" height="9" rx="1.5" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
      <circle cx="12" cy="15.5" r="1.2" />
    </svg>
  )
}

const CAPABILITIES = [
  { glyph: 'ways' as const, title: 'Three ways in', body: 'Describe it, photograph it, or sketch it — KimCad reads all three into a design.' },
  { glyph: 'check' as const, title: 'Checked for printing', body: 'Every part is validated against your printer before it can be sliced — no surprises.' },
  { glyph: 'print' as const, title: 'Slice & print', body: 'Download a print-ready file, or send it straight to your printer from the app.' },
  { glyph: 'local' as const, title: 'Yours, on your machine', body: 'No account, no cloud by default. Nothing you make leaves your computer.' },
]

export default function Landing({
  onSubmit,
  busy,
  initialValue = '',
}: {
  onSubmit: (prompt: string) => void
  busy: boolean
  /** UX-001: a preserved draft (e.g. after a cancelled first design) re-seeds the box. */
  initialValue?: string
}) {
  const [value, setValue] = useState(initialValue)
  // UX-108 (stage-BCD gate): the "picked up" note describes the SEEDED text — hide it the
  // moment the user edits (especially after clearing the box, where it read as a lie).
  const [edited, setEdited] = useState(false)

  function submit(e: FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (trimmed && !busy) onSubmit(trimmed)
  }

  // UX-104 (stage-BCD gate): same keyboard contract as the refine box — Enter sends,
  // Shift+Enter is a newline (with the same visible hint).
  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const trimmed = value.trim()
      if (trimmed && !busy) onSubmit(trimmed)
    }
  }

  return (
    <main id="kimcad-main" className="kc-landing">
      <div className="kc-landing-inner">
        <span className="kc-badge">
          <span className="kc-badge-dot" aria-hidden="true" />
          Ready to print in ~15 minutes · no CAD skills
        </span>
        <h1 className="kc-hero-title">What do you want to make today?</h1>
        <p className="kc-hero-sub">
          Describe a functional part in plain words — I&rsquo;ll design it, check that it&rsquo;s
          actually printable, and get it ready for your printer. Runs entirely on your machine.
        </p>

        {/* UX-002: surface a down model BEFORE the user invests a prompt + a wait. */}
        <ModelHealthPill />

        {initialValue && !edited && (
          <p className="kc-muted-note kc-draft-note">Picked up where you left off.</p>
        )}
        <form className="kc-input-card" onSubmit={submit}>
          <textarea
            className="kc-input"
            rows={2}
            placeholder="e.g. a wall-mounted holder for a 1 kg filament spool"
            aria-label="Describe the part you want"
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              setEdited(true)
            }}
            onKeyDown={handleKeyDown}
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
        <span className="kc-key-hint">Enter to send · Shift+Enter for a new line</span>

        {/* Slice 7: the photo on-ramp — a rough, editable seed from a local-vision read of a photo.
            Stage 9 adds the sketch on-ramp beside it (a dimensioned sketch reads shape + written
            sizes). Both secondary to the text path; both pre-fill the same design flow. */}
        <div className="kc-onramps">
          <PhotoOnramp onSeed={onSubmit} disabled={busy} variant="landing" kind="photo" />
          <PhotoOnramp onSeed={onSubmit} disabled={busy} variant="landing" kind="sketch" />
        </div>

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

        <section className="kc-capabilities" aria-label="What KimCad does">
          {CAPABILITIES.map((c) => (
            <div key={c.title} className="kc-cap">
              <span className="kc-cap-icon" aria-hidden="true">
                <CapGlyph name={c.glyph} />
              </span>
              <span className="kc-cap-title">{c.title}</span>
              <span className="kc-cap-body">{c.body}</span>
            </div>
          ))}
        </section>
      </div>
    </main>
  )
}
