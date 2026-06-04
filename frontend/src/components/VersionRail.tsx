import type { DesignVersion } from '../api'

// A compact pill-strip showing all versions of the current design session (v1, v2, v3…).
// The active version is highlighted; clicking a prior pill restores that version. An undo
// button steps back one version. A compare button (2+ versions) shows a text diff of the
// two most-recent version summaries directly in the strip.
//
// Stage 8.5 Slice 2: "describe a change" is non-destructive — every successful refinement
// creates a new version here, so the user can always step back to an earlier design.

export default function VersionRail({
  versions,
  versionIdx,
  onSwitch,
}: {
  versions: DesignVersion[]
  versionIdx: number
  onSwitch: (idx: number) => void
}) {
  if (versions.length < 2) return null  // only show when there's something to navigate

  const canUndo = versionIdx > 0
  const canRedo = versionIdx < versions.length - 1

  return (
    <div className="kc-version-rail" role="navigation" aria-label="Design versions">
      <span className="kc-version-label" aria-hidden="true">Versions</span>

      <div className="kc-version-pills">
        {versions.map((v, i) => (
          <button
            key={i}
            type="button"
            className={`kc-version-pill${i === versionIdx ? ' kc-version-pill-active' : ''}`}
            onClick={() => onSwitch(i)}
            title={v.label}
            aria-current={i === versionIdx ? 'true' : undefined}
            aria-label={`Version ${v.index}: ${v.label}`}
          >
            v{v.index}
          </button>
        ))}
      </div>

      <div className="kc-version-actions">
        <button
          type="button"
          className="kc-version-step"
          onClick={() => onSwitch(versionIdx - 1)}
          disabled={!canUndo}
          aria-label="Undo to previous version"
          title="Undo"
        >
          ← Undo
        </button>
        {canRedo && (
          <button
            type="button"
            className="kc-version-step"
            onClick={() => onSwitch(versionIdx + 1)}
            aria-label="Redo to next version"
            title="Redo"
          >
            Redo →
          </button>
        )}
      </div>
    </div>
  )
}
