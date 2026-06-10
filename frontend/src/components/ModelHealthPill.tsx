import { useCallback, useEffect, useRef, useState } from 'react'
import { getModelStatus, type ModelStatus } from '../api'

// UX-002 (2026-06-09 audit): a down model must be visible BEFORE the user invests a prompt
// and a multi-minute wait. Shown only when the local AI isn't ready — silence means healthy.
//
// UX-A-001/002 (stage-A gate): the status region is PERSISTENTLY MOUNTED and only its text
// changes, so screen readers reliably announce both the warning and the recovery; and
// "Check again" never unmounts under the user's finger (it no-ops while a check is in
// flight instead of disabling, so keyboard focus is preserved).
export default function ModelHealthPill() {
  const [model, setModel] = useState<ModelStatus | null>(null)
  const [checking, setChecking] = useState(true)
  // Announce "ready" only after a recovery the user witnessed — not on a healthy mount.
  const everWarned = useRef(false)

  const check = useCallback(() => {
    setChecking(true)
    getModelStatus()
      .then((m) => setModel(m))
      .catch(() => setModel(null)) // can't probe — stay silent rather than cry wolf
      .finally(() => setChecking(false))
  }, [])

  useEffect(() => check(), [check])

  // UX-902 (stage-9 gate): the photo/sketch on-ramps use a SECOND local model — warn when
  // it's missing too (vision_present === false; absent/undefined means unknown, stay quiet),
  // or the user only learns at the moment their image fails.
  const problem =
    model !== null && model.backend !== 'cloud' && !(model.running && model.model_present)
      ? !model.running
        ? 'Your local AI isn’t running yet — start Ollama to design.'
        : // DOC-1005 (stage-10 gate): the in-app download is the first-named path now.
          `The model isn’t downloaded yet — the setup wizard’s Download button fetches it (or run “ollama pull ${model.model}”).`
      : model !== null && model.backend !== 'cloud' && model.vision_present === false
        ? `Photos and sketches need one more download — the setup wizard’s Download button fetches it (or run “ollama pull ${model.vision_model}”). Designing in words works now.`
        : null
  if (problem) everWarned.current = true

  if (!problem) {
    // Healthy/unknown: visually nothing, but the live region stays mounted so the
    // recovery is announced ("ready") after a warning the user saw.
    return (
      <p className="kc-sr-only" role="status">
        {everWarned.current && !checking ? 'Your local AI is ready.' : ''}
      </p>
    )
  }

  return (
    <p className="kc-model-pill" role="status">
      <span className="kc-statdot kc-statdot-warn" aria-hidden="true" />
      {problem}{' '}
      <button
        type="button"
        className="kc-link-btn kc-link-btn-warn"
        aria-disabled={checking || undefined}
        onClick={() => {
          if (!checking) check()
        }}
      >
        {checking ? 'Checking…' : 'Check again'}
      </button>
    </p>
  )
}
