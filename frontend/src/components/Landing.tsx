// The landing (empty) screen: the entry point where the user describes a part.
//
// Slice 2 builds the screen and Workshop styling. The textarea, "Design it" button, and the
// example chips become live in Slice 4, when the prompt → /api/design flow is wired; for now
// they are presentational (no misleading handlers). The photo on-ramp is a later stage (image
// intake) and is intentionally absent here.
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

export default function Landing() {
  return (
    <main className="kc-landing">
      <div className="kc-landing-inner">
        <span className="kc-badge">Local-first · runs entirely on your machine</span>
        <h1 className="kc-hero-title">What do you want to make today?</h1>
        <p className="kc-hero-sub">
          Describe a functional part in plain words. KimCad designs it, checks that it&rsquo;s
          actually printable, and gets it ready for your printer.
        </p>

        <div className="kc-input-card">
          <textarea
            className="kc-input"
            rows={2}
            placeholder="e.g. a wall-mounted holder for a 1 kg filament spool"
            aria-label="Describe the part you want"
          />
          <button type="button" className="kc-btn kc-btn-accent kc-design-btn">
            Design it
            <SendGlyph />
          </button>
        </div>

        <div className="kc-examples">
          <span className="kc-examples-label">Try</span>
          {EXAMPLES.map((example) => (
            <button key={example} type="button" className="kc-chip">
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
