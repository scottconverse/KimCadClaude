import type { DesignVersion } from '../api'

// Pill-strip showing all versions (v1, v2, v3…). Hidden until there are 2+ versions.
// Undo/Redo step through versions; Compare shows a summary diff card in the thread.
export default function VersionRail({
  versions,
  versionIdx,
  onSwitch,
  onCompare,
}: {
  versions: DesignVersion[]
  versionIdx: number
  onSwitch: (idx: number) => void
  onCompare: (aIdx: number, bIdx: number) => void
}) {
  if (versions.length < 2) return null

  const canUndo = versionIdx > 0
  const canRedo = versionIdx < versions.length - 1
  // Compare defaults to the two most-recent versions.
  const compareA = Math.max(0, versions.length - 2)
  const compareB = versions.length - 1

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
        <button
          type="button"
          className="kc-version-step kc-version-compare"
          onClick={() => onCompare(compareA, compareB)}
          aria-label={`Compare v${versions[compareA].index} and v${versions[compareB].index}`}
          title="Compare the two most-recent versions"
        >
          Compare
        </button>
      </div>
    </div>
  )
}
