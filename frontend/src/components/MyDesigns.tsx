import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  deleteDesign,
  duplicateDesign,
  exportDesignUrl,
  getDesigns,
  importDesign,
  isAbortError,
  renameDesign,
  type SavedDesignSummary,
} from '../api'

type SortKey = 'newest' | 'oldest' | 'name'

// Stage 8.5 Slice 1 — the "My Designs" library: a thumbnail grid of saved designs. Click a card to
// reopen it (the app routes to '#/design/<id>' and restores the part + its sliders); rename inline;
// duplicate or delete. Replaces the old behavior where your work vanished the moment you moved on.

function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function DesignCard({
  design,
  onOpen,
  onChanged,
}: {
  design: SavedDesignSummary
  onOpen: (id: string) => void
  onChanged: () => void
}) {
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(design.name)
  const [busy, setBusy] = useState(false)
  // UX-007: a per-card error so a failed Rename/Duplicate/Delete can't silently read as success.
  const [err, setErr] = useState<string | null>(null)
  // Two-step delete: the first click arms it, a second confirms — so a saved design isn't lost to
  // a single accidental click. Auto-disarms after a few seconds.
  const [confirmDelete, setConfirmDelete] = useState(false)
  useEffect(() => {
    if (!confirmDelete) return
    const t = window.setTimeout(() => setConfirmDelete(false), 3500)
    return () => window.clearTimeout(t)
  }, [confirmDelete])

  async function commitRename() {
    const next = name.trim()
    setRenaming(false)
    if (next && next !== design.name) {
      setErr(null)
      try {
        const res = await renameDesign(design.id, next)
        if (res && res.ok === false) {
          setErr('Couldn’t rename — try again.')
          setName(design.name)
        }
      } catch {
        setErr('Couldn’t rename — try again.')
        setName(design.name)
      }
      onChanged()
    } else {
      setName(design.name)
    }
  }

  // Run a card action; surface a per-card error if it throws or returns {ok:false} (UX-007).
  async function act(label: string, fn: () => Promise<{ ok?: boolean } | unknown>) {
    setBusy(true)
    setErr(null)
    try {
      const res = (await fn()) as { ok?: boolean } | null
      if (res && typeof res === 'object' && 'ok' in res && res.ok === false) {
        setErr(`Couldn’t ${label} — try again.`)
      }
    } catch {
      setErr(`Couldn’t ${label} — try again.`)
    } finally {
      setBusy(false)
      onChanged()
    }
  }

  return (
    <div className={`kc-design-card${busy ? ' kc-design-card-busy' : ''}`}>
      <button
        type="button"
        className="kc-design-open"
        onClick={() => onOpen(design.id)}
        aria-label={`Open ${design.name}`}
      >
        {design.thumb_url ? (
          <img className="kc-design-thumb" src={design.thumb_url} alt="" loading="lazy" />
        ) : (
          <div className="kc-design-thumb kc-design-thumb-empty" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor"
              strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2 21 7v10l-9 5-9-5V7Z" />
              <path d="M3 7l9 5 9-5" />
              <path d="M12 12v10" />
            </svg>
            <span>{design.object_type || 'part'}</span>
          </div>
        )}
      </button>

      <div className="kc-design-meta">
        {renaming ? (
          <input
            className="kc-design-rename"
            value={name}
            autoFocus
            onChange={(e) => setName(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitRename()
              if (e.key === 'Escape') {
                setName(design.name)
                setRenaming(false)
              }
            }}
            aria-label="Design name"
          />
        ) : (
          <button
            type="button"
            className="kc-design-name"
            onClick={() => onOpen(design.id)}
            title={design.name}
          >
            {design.name}
          </button>
        )}
        <span className="kc-design-date">{formatDate(design.created_at)}</span>
      </div>

      <div className="kc-design-actions">
        <button type="button" className="kc-design-act" onClick={() => setRenaming(true)}>
          Rename
        </button>
        <button type="button" className="kc-design-act" onClick={() => act('duplicate', () => duplicateDesign(design.id))}>
          Duplicate
        </button>
        <a
          className="kc-design-act"
          href={exportDesignUrl(design.id)}
          download
          title="Download a .kimcad backup you can re-import — not a printable STL"
        >
          Export (.kimcad)
        </a>
        {confirmDelete ? (
          <>
            <button
              type="button"
              className="kc-design-act kc-design-act-danger"
              onClick={() => {
                setConfirmDelete(false)
                void act('delete', () => deleteDesign(design.id))
              }}
            >
              Delete?
            </button>
            <button type="button" className="kc-design-act" onClick={() => setConfirmDelete(false)}>
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            className="kc-design-act kc-design-act-danger"
            onClick={() => setConfirmDelete(true)}
          >
            Delete
          </button>
        )}
      </div>
      {err && (
        <p className="kc-design-err" role="alert">
          {err}
        </p>
      )}
    </div>
  )
}

export default function MyDesigns({
  onOpen,
  onNew,
}: {
  onOpen: (id: string) => void
  onNew: () => void
}) {
  const [designs, setDesigns] = useState<SavedDesignSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<SortKey>('newest')
  const [importing, setImporting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const importAbortRef = useRef<AbortController | null>(null)

  const load = useCallback(() => {
    getDesigns()
      .then((r) => {
        setDesigns(r.designs)
        setError(null)
      })
      .catch(() => setError("Couldn't load your designs."))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Filter (by name) + sort, derived from the loaded list (the server returns newest-first).
  const shown = useMemo(() => {
    if (designs === null) return null
    const q = query.trim().toLowerCase()
    const filtered = q ? designs.filter((d) => d.name.toLowerCase().includes(q)) : designs.slice()
    if (sort === 'name') filtered.sort((a, b) => a.name.localeCompare(b.name))
    else if (sort === 'oldest') filtered.sort((a, b) => a.created_at.localeCompare(b.created_at))
    else filtered.sort((a, b) => b.created_at.localeCompare(a.created_at)) // newest
    return filtered
  }, [designs, query, sort])

  async function handleImportFile(file: File | undefined) {
    if (!file) return
    const controller = new AbortController()
    importAbortRef.current = controller
    setImporting(true)
    try {
      const r = await importDesign(file, controller.signal)
      load()
      onOpen(r.id) // open the freshly imported design
    } catch (e) {
      if (!isAbortError(e)) setError(e instanceof Error ? e.message : "That file couldn't be imported.")
      // a cancel just returns to the Import button — no error
    } finally {
      if (importAbortRef.current === controller) importAbortRef.current = null
      setImporting(false)
      if (fileRef.current) fileRef.current.value = '' // allow re-importing the same file
    }
  }

  function cancelImport() {
    importAbortRef.current?.abort()
  }

  // Abort an in-flight import on unmount (navigating away) so it doesn't finish in the background and
  // yank the user into the imported design — matches ExportPanel/PhotoOnramp.
  useEffect(() => () => importAbortRef.current?.abort(), [])

  const hasAny = designs !== null && designs.length > 0

  return (
    <main className="kc-mydesigns">
      <div className="kc-mydesigns-head">
        <h1 className="kc-mydesigns-title">My Designs</h1>
        <div className="kc-mydesigns-headactions">
          <input
            ref={fileRef}
            type="file"
            accept=".kimcad,application/zip"
            className="kc-sr-only"
            onChange={(e) => handleImportFile(e.target.files?.[0])}
          />
          <button
            type="button"
            className="kc-btn kc-btn-ghost"
            onClick={() => fileRef.current?.click()}
            disabled={importing}
          >
            {importing ? 'Importing…' : 'Import'}
          </button>
          {importing && (
            <button type="button" className="kc-btn kc-btn-ghost" onClick={cancelImport}>
              Cancel
            </button>
          )}
          <button type="button" className="kc-btn kc-btn-accent" onClick={onNew}>
            New design
          </button>
        </div>
      </div>

      {hasAny && (
        <div className="kc-mydesigns-toolbar">
          <input
            type="search"
            className="kc-mydesigns-search"
            placeholder="Search your designs…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search your designs"
          />
          <label className="kc-mydesigns-sort">
            <span className="kc-sr-only">Sort by</span>
            <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="name">Name (A–Z)</option>
            </select>
          </label>
        </div>
      )}

      {error && <p className="kc-muted-note" role="alert">{error}</p>}

      {designs === null && !error && <p className="kc-muted-note">Loading your designs…</p>}

      {designs !== null && designs.length === 0 && (
        <div className="kc-mydesigns-empty">
          <p>Nothing saved yet.</p>
          <p className="kc-muted-note">
            Describe a part and it’s kept here automatically — come back to it anytime.
          </p>
          <button type="button" className="kc-btn kc-btn-accent" onClick={onNew}>
            Design your first part
          </button>
        </div>
      )}

      {hasAny && shown !== null && shown.length === 0 && (
        <p className="kc-muted-note">No designs match “{query}”.</p>
      )}

      {shown !== null && shown.length > 0 && (
        <div className="kc-design-grid">
          {shown.map((d) => (
            <DesignCard key={d.id} design={d} onOpen={onOpen} onChanged={load} />
          ))}
        </div>
      )}
    </main>
  )
}
