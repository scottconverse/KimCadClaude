import { useEffect, useMemo, useRef, useState } from 'react'
import { getTemplates, type TemplateFamilyInfo } from '../api'

// UI-v2 slice 3 (#23) — the part library browser. A searchable grid of every shipped
// template family (read live from /api/templates, so the catalog work in #19 shows up here
// automatically). Picking a card submits the family's seed prompt through the NORMAL design
// flow — the library is a discovery surface, not a separate pipeline.

export default function LibraryModal({
  onPick,
  onClose,
}: {
  /** Submit the picked family's seed prompt (the caller routes it like any typed prompt). */
  onPick: (seed: string) => void
  onClose: () => void
}) {
  const [families, setFamilies] = useState<TemplateFamilyInfo[] | null>(null)
  const [error, setError] = useState(false)
  const [query, setQuery] = useState('')
  const dialogRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let cancelled = false
    getTemplates()
      .then((t) => { if (!cancelled) setFamilies(t.families) })
      .catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [])

  // Esc closes; focus starts in the search box and returns to the opener on close.
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null
    searchRef.current?.focus()
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previouslyFocused?.focus?.()
    }
  }, [onClose])

  const filtered = useMemo(() => {
    if (!families) return []
    const q = query.trim().toLowerCase()
    if (!q) return families
    return families.filter(
      (f) =>
        f.name.toLowerCase().includes(q) ||
        f.summary.toLowerCase().includes(q) ||
        f.examples.some((e) => e.toLowerCase().includes(q)) ||
        f.tier.includes(q),
    )
  }, [families, query])

  return (
    <div className="kc-modal-backdrop" onClick={onClose}>
      <div
        ref={dialogRef}
        className="kc-library-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="kc-library-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="kc-library-head">
          <h2 id="kc-library-title" className="kc-library-title">Part library</h2>
          <input
            ref={searchRef}
            type="search"
            className="kc-library-search"
            placeholder="Search parts — “tray”, “hook”, “spacer”…"
            aria-label="Search the part library"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="button" className="kc-btn-sm" onClick={onClose}>Close</button>
        </div>
        <p className="kc-muted-note kc-library-sub">
          Every part here is a measured, adjustable template — pick one and shape it with the
          sliders. Or just describe what you want in your own words.
        </p>
        {error ? (
          <p className="kc-muted-note" role="alert">
            Couldn&rsquo;t load the library — the design box still works; just describe your part.
          </p>
        ) : families === null ? (
          <p className="kc-muted-note">Loading the library…</p>
        ) : filtered.length === 0 ? (
          <p className="kc-muted-note">
            Nothing in the library matches &ldquo;{query}&rdquo; — describe it in the design box
            instead; KimCad designs beyond the library too.
          </p>
        ) : (
          <div className="kc-library-grid">
            {filtered.map((f) => (
              <button
                key={f.name}
                type="button"
                className="kc-library-card"
                onClick={() => { onPick(f.seed); onClose() }}
              >
                <span className="kc-library-card-name">
                  {f.examples[0]}
                  {f.tier === 'baseline' && (
                    <span
                      className="kc-library-tier kc-library-tier-baseline"
                      title="Real, verified geometry — but check dimensions, fit & load before real use."
                    >
                      Verify before use
                    </span>
                  )}
                </span>
                <span className="kc-library-card-sum">{f.summary}</span>
                <span className="kc-library-card-meta">
                  {f.param_count} adjustable {f.param_count === 1 ? 'dimension' : 'dimensions'}
                  {f.examples.length > 1 && <> · also: {f.examples.slice(1, 3).join(', ')}</>}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
