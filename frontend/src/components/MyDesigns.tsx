import { useCallback, useEffect, useState } from 'react'
import {
  deleteDesign,
  duplicateDesign,
  getDesigns,
  renameDesign,
  type SavedDesignSummary,
} from '../api'

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
      await renameDesign(design.id, next).catch(() => {})
      onChanged()
    } else {
      setName(design.name)
    }
  }

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    await fn().catch(() => {})
    setBusy(false)
    onChanged()
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
            {design.object_type || 'part'}
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
        <button type="button" className="kc-design-act" onClick={() => act(() => duplicateDesign(design.id))}>
          Duplicate
        </button>
        {confirmDelete ? (
          <>
            <button
              type="button"
              className="kc-design-act kc-design-act-danger"
              onClick={() => {
                setConfirmDelete(false)
                void act(() => deleteDesign(design.id))
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

  return (
    <main className="kc-mydesigns">
      <div className="kc-mydesigns-head">
        <h1 className="kc-mydesigns-title">My Designs</h1>
        <button type="button" className="kc-btn kc-btn-accent" onClick={onNew}>
          New design
        </button>
      </div>

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

      {designs !== null && designs.length > 0 && (
        <div className="kc-design-grid">
          {designs.map((d) => (
            <DesignCard key={d.id} design={d} onOpen={onOpen} onChanged={load} />
          ))}
        </div>
      )}
    </main>
  )
}
