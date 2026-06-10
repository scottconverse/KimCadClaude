import { useCallback, useEffect, useState } from 'react'
import { getModelStatus, type ModelStatus } from '../api'

// UX-002 (2026-06-09 audit): a down model must be visible BEFORE the user invests a prompt
// and a multi-minute wait. This pill sits on the Landing and shows only when the local AI
// isn't ready — silence means healthy (no badge noise on the happy path). "Check again"
// re-probes without a reload, mirroring the wizard's affordance.
export default function ModelHealthPill() {
  const [model, setModel] = useState<ModelStatus | null>(null)
  const [checking, setChecking] = useState(true)

  const check = useCallback(() => {
    setChecking(true)
    getModelStatus()
      .then((m) => setModel(m))
      .catch(() => setModel(null)) // can't probe — stay silent rather than cry wolf
      .finally(() => setChecking(false))
  }, [])

  useEffect(() => check(), [check])

  if (checking || model === null || model.backend === 'cloud') return null
  if (model.running && model.model_present) return null

  const problem = !model.running
    ? 'Your local AI isn’t running yet — start Ollama to design.'
    : `The model isn’t pulled yet — run “ollama pull ${model.model}” first.`

  return (
    <p className="kc-model-pill" role="status">
      <span className="kc-statdot kc-statdot-warn" aria-hidden="true" />
      {problem}{' '}
      <button type="button" className="kc-link-btn" onClick={check}>
        Check again
      </button>
    </p>
  )
}
