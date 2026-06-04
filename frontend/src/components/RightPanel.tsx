import { type CSSProperties, useEffect, useRef, useState } from 'react'
import type { DesignResponse, ParamSpec, ReadinessPayload } from '../api'
import { gateLabel, gateTone, isFailureStatus, readinessTone } from '../designStatus'
import ExportPanel from './ExportPanel'

// Right column — parameters + printability, rendered from the design result.
//
// Stage 5: a TEMPLATE-backed design gets live sliders (one per backend `parameters` entry). A
// drag updates the slider immediately and, ~150 ms after the last move, posts the values to the
// deterministic re-render endpoint (via `onRerender`) — no model call. The server's clamped
// values become the new truth (the sliders re-sync to them). An LLM-backed part has no
// parameters, so it keeps a clear read-only state. The printability card shows the gate verdict,
// the target-vs-actual dimensions, and any findings.

const RERENDER_DEBOUNCE_MS = 150

function formatValue(value: number, spec: ParamSpec): string {
  if (spec.integer) return String(Math.round(value))
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

/** Clamp and round a raw number to the spec's valid range. */
function clampToSpec(raw: number, spec: ParamSpec): number {
  const clamped = Math.max(spec.min, Math.min(spec.max, raw))
  return spec.integer ? Math.round(clamped) : clamped
}

// Slice 3: the value label is now clickable — it opens an inline text input so the user can
// type an exact number instead of dragging. Enter/blur commits (clamping to the valid range);
// Escape cancels. Arrow keys on the slider already nudge by step (native range behaviour).
function SliderRow({
  spec,
  value,
  onChange,
}: {
  spec: ParamSpec
  value: number
  onChange: (name: string, value: number) => void
}) {
  const span = spec.max - spec.min
  const pct = span > 0 ? Math.min(100, Math.max(0, ((value - spec.min) / span) * 100)) : 0

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [inputError, setInputError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  function startEdit() {
    setDraft(formatValue(value, spec))
    setInputError(null)
    setEditing(true)
    setTimeout(() => {
      inputRef.current?.select()
    }, 0)
  }

  function commitEdit() {
    setEditing(false)
    setInputError(null)
    const raw = parseFloat(draft)
    if (Number.isNaN(raw)) return // silently revert to current value on empty/garbage
    // clampToSpec handles both in-range and out-of-range values; live error was shown while typing.
    onChange(spec.name, clampToSpec(raw, spec))
  }

  function handleDraftChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value
    setDraft(val)
    const n = parseFloat(val)
    if (!Number.isNaN(n) && (n < spec.min || n > spec.max)) {
      setInputError(`${spec.min}–${spec.max}${spec.unit ? ` ${spec.unit}` : ''}`)
    } else {
      setInputError(null)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') { e.preventDefault(); commitEdit() }
    if (e.key === 'Escape') { setEditing(false); setInputError(null) }
  }

  return (
    <div className="kc-prow">
      <div className="kc-plabel">
        <span>
          {spec.label}
          {spec.axis && <i className="kc-axis">{spec.axis}</i>}
        </span>
        {editing ? (
          <span className="kc-pval-edit-wrap">
            <input
              ref={inputRef}
              type="number"
              className={`kc-pval-input${inputError ? ' kc-pval-input-err' : ''}`}
              value={draft}
              min={spec.min}
              max={spec.max}
              step={spec.step}
              aria-label={`${spec.label} value${spec.unit ? ` in ${spec.unit}` : ''}`}
              aria-invalid={inputError ? 'true' : undefined}
              aria-describedby={inputError ? `${spec.name}-err` : undefined}
              onChange={handleDraftChange}
              onBlur={commitEdit}
              onKeyDown={handleKeyDown}
            />
            {spec.unit && <i className="kc-pval-unit">{spec.unit}</i>}
            {inputError && (
              <span id={`${spec.name}-err`} className="kc-pval-err" role="alert">
                {inputError}
              </span>
            )}
          </span>
        ) : (
          <button
            type="button"
            className="kc-pval kc-pval-btn"
            onClick={startEdit}
            title={`Click to type an exact value (${spec.min}–${spec.max}${spec.unit ? ` ${spec.unit}` : ''})`}
            aria-label={`${spec.label}: ${formatValue(value, spec)}${spec.unit ? ` ${spec.unit}` : ''}. Click to edit.`}
          >
            {formatValue(value, spec)}
            {spec.unit && <i>{spec.unit}</i>}
          </button>
        )}
      </div>
      <input
        type="range"
        className="kc-range"
        name={spec.name}
        aria-label={spec.label}
        aria-valuetext={`${formatValue(value, spec)}${spec.unit ? ` ${spec.unit}` : ''}`}
        min={spec.min}
        max={spec.max}
        step={spec.step}
        value={value}
        style={{ '--pct': `${pct}%` } as CSSProperties}
        onChange={(e) => { setEditing(false); onChange(spec.name, Number(e.target.value)) }}
      />
    </div>
  )
}

function ParametersCard({
  result,
  rerendering,
  rerenderError,
  onRerender,
}: {
  result: DesignResponse | null
  rerendering: boolean
  rerenderError: string | null
  onRerender: (values: Record<string, number>) => void
}) {
  const plan = result?.plan
  const parameters = result?.parameters

  // Local slider values, re-synced to the server's truth whenever the result's parameters change
  // (a new design, or the clamped values a re-render returns). `valuesRef` mirrors them so the
  // debounced post always sends the latest merged set without a stale closure.
  const [values, setValues] = useState<Record<string, number>>({})
  const valuesRef = useRef<Record<string, number>>({})
  const timer = useRef<number | null>(null)

  useEffect(() => {
    const next = parameters
      ? Object.fromEntries(parameters.map((p) => [p.name, p.value]))
      : {}
    valuesRef.current = next
    setValues(next)
  }, [parameters])

  // Clear any pending debounce on unmount so it can't fire after the card is gone.
  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current)
  }, [])

  function handleSlide(name: string, raw: number) {
    const next = { ...valuesRef.current, [name]: raw }
    valuesRef.current = next
    setValues(next)
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => {
      timer.current = null
      onRerender({ ...valuesRef.current })
    }, RERENDER_DEBOUNCE_MS)
  }

  return (
    <section className="kc-card">
      <div className="kc-card-hd">
        <h2 className="kc-card-title">Parameters</h2>
        {rerendering && (
          <span className="kc-param-updating" role="status">
            Re-rendering…
          </span>
        )}
      </div>

      {parameters && parameters.length > 0 ? (
        <>
          <p className="kc-card-sub">
            Drag a slider — the part re-renders locally in under a second, no AI round-trip.
          </p>
          <div className="kc-params">
            {parameters.map((p) => (
              <SliderRow
                key={p.name}
                spec={p}
                value={values[p.name] ?? p.value}
                onChange={handleSlide}
              />
            ))}
          </div>
          {rerenderError && (
            <p className="kc-muted-note kc-param-error" role="alert">
              That change didn&rsquo;t render — your last version is still here. Nudge a slider to
              try again. <span className="kc-error-detail">({rerenderError})</span>
            </p>
          )}
        </>
      ) : plan ? (
        <>
          <dl className="kc-paramlist">
            <div className="kc-paramrow">
              <dt>Type</dt>
              <dd>{plan.object_type}</dd>
            </div>
            {plan.target_bbox_mm && (
              <div className="kc-paramrow">
                <dt>Size</dt>
                <dd className="kc-mono">
                  {plan.target_bbox_mm.map((n) => Math.round(n)).join(' × ')} mm
                </dd>
              </div>
            )}
          </dl>
          {/* Slice 3 / Slice 2: LLM-backed parts have no sliders, but the refine input in the
              conversation panel lets the user describe exact changes and get a new version. */}
          <p className="kc-muted-note kc-param-hint">
            No live sliders for this part — it was generated directly, not from a parametric
            template. To adjust it, use the conversation on the left: type an exact change like
            <em> "make it 10mm taller"</em> or <em>"add M3 mounting holes"</em> and a new version
            will appear.
          </p>
        </>
      ) : isFailureStatus(result?.status) ? (
        <p className="kc-muted-note kc-param-error" role="status">
          No part was produced, so there&rsquo;s nothing to adjust. Try describing it a little
          differently on the left.
        </p>
      ) : (
        <p className="kc-muted-note">
          The part&rsquo;s adjustable parameters will appear here once it&rsquo;s designed.
        </p>
      )}
    </section>
  )
}

// Stage 7 — the Smart Mesh readiness card: the synthesized "should I print this?" verdict that
// sits atop the detailed printability breakdown. A score gauge, a plain verdict, a confidence
// badge, the risks, concrete recommendations, an optional history line, and an honest attribution
// of what backed the call (the gate alone, or the PrintProof3D engine).

const CONFIDENCE_BLURB: Record<string, string> = {
  High: 'Validated by the PrintProof3D engine.',
  Medium: 'From KimCad’s printability gate.',
  Low: 'Provisional — the mesh could only be partly analyzed.',
}

// A screen-reader-only severity word per risk tone, so the warn/red tier isn't conveyed by the
// dot color alone (WCAG 1.4.1). The risk title/detail carry the rest of the meaning.
const RISK_TONE_WORD: Record<string, string> = {
  fail: 'Critical risk',
  warn: 'Warning',
  neutral: 'Note',
}

function ScoreGauge({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)))
  // A semicircular arc; pathLength=100 lets the dash be the score directly, independent of the
  // path's real length. The fill color is scoped to the card's tone class in CSS.
  return (
    <div className="kc-gauge-wrap">
      <svg
        className="kc-gauge"
        viewBox="0 0 120 70"
        role="img"
        aria-label={`Readiness score ${clamped} out of 100`}
      >
        <path className="kc-gauge-track" d="M10 60 A50 50 0 0 1 110 60" />
        <path
          className="kc-gauge-fill"
          d="M10 60 A50 50 0 0 1 110 60"
          pathLength={100}
          strokeDasharray={`${clamped} 100`}
        />
      </svg>
      <div className="kc-gauge-num">
        {clamped}
        <i>/100</i>
      </div>
    </div>
  )
}

function ReadinessBody({ readiness }: { readiness: ReadinessPayload }) {
  const tone = readinessTone(readiness.tone)
  return (
    <div className={`kc-readiness kc-rtone-${tone}`}>
      <ScoreGauge score={readiness.score} />
      <p className="kc-readiness-verdict">{readiness.verdict}</p>
      {readiness.confidence && (
        <p className="kc-readiness-conf">
          <span className="kc-conf-badge">{readiness.confidence} confidence</span>
          <span className="kc-conf-blurb">{CONFIDENCE_BLURB[readiness.confidence] ?? ''}</span>
        </p>
      )}

      {readiness.risks.length > 0 && (
        <div className="kc-readiness-sec">
          <h3 className="kc-readiness-h">Risks</h3>
          <ul className="kc-risks">
            {readiness.risks.map((r) => {
              const rtone = readinessTone(r.tone)
              return (
                <li key={`${r.title}:${r.detail}`} className={`kc-risk kc-rtone-${rtone}`}>
                  <span className="kc-risk-dot" aria-hidden="true" />
                  <span className="kc-risk-text">
                    <span className="kc-sr-only">{RISK_TONE_WORD[rtone] ?? 'Note'}: </span>
                    <b>{r.title}</b>
                    {r.detail && <span className="kc-risk-detail">{r.detail}</span>}
                  </span>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {readiness.recommendations.length > 0 && (
        <div className="kc-readiness-sec">
          <h3 className="kc-readiness-h">Recommendations</h3>
          <ul className="kc-recs">
            {readiness.recommendations.map((rec) => (
              <li key={rec} className="kc-rec">
                <span className="kc-rec-arrow" aria-hidden="true">
                  →
                </span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {readiness.comparison && <p className="kc-readiness-history">{readiness.comparison}</p>}
      {readiness.attribution && (
        <p className="kc-readiness-attr">via {readiness.attribution}</p>
      )}
    </div>
  )
}

function ReadinessCard({ result }: { result: DesignResponse | null }) {
  const readiness = result?.report?.readiness
  return (
    <section className="kc-card">
      <h2 className="kc-card-title">Readiness</h2>
      {readiness ? (
        <ReadinessBody readiness={readiness} />
      ) : isFailureStatus(result?.status) ? (
        <p className="kc-muted-note" role="status">
          No part to assess — the last attempt didn&rsquo;t produce a model.
        </p>
      ) : (
        <p className="kc-muted-note">
          A print-readiness score — with the risks and concrete next steps — appears here once a
          part is designed.
        </p>
      )}
    </section>
  )
}

function PrintabilityCard({ result }: { result: DesignResponse | null }) {
  const report = result?.report
  return (
    <section className="kc-card">
      <h2 className="kc-card-title">Printability</h2>
      {report ? (
        <>
          <span className={`kc-status-badge kc-tone-${gateTone(report.gate_status)}`}>
            Gate: {gateLabel(report.gate_status)}
          </span>
          {report.headline && <p className="kc-muted-note">{report.headline}</p>}

          {report.dims.length > 0 && (
            <table className="kc-dims">
              <thead>
                <tr>
                  <th scope="col">Axis</th>
                  <th scope="col">Target</th>
                  <th scope="col">Actual</th>
                </tr>
              </thead>
              <tbody>
                {report.dims.map((d) => (
                  <tr key={d.axis} className={d.ok ? undefined : 'kc-dim-off'}>
                    <td>{d.axis}</td>
                    <td className="kc-mono">{d.target}</td>
                    <td className="kc-mono">
                      {d.actual}
                      {d.ok ? '' : ' ⚠'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {report.findings.length > 0 && (
            <ul className="kc-findings">
              {report.findings.map((f) => (
                <li key={`${f.code}:${f.message}`} className={`kc-finding kc-finding-${f.level}`}>
                  {f.message}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : isFailureStatus(result?.status) ? (
        <p className="kc-muted-note" role="status">
          No part to check — the last attempt didn&rsquo;t produce a model.
        </p>
      ) : (
        <p className="kc-muted-note">
          The printability check — dimensions, wall thickness, build-volume fit — appears here
          after a part is designed.
        </p>
      )}
    </section>
  )
}

export default function RightPanel({
  result,
  rerendering,
  rerenderError,
  onRerender,
}: {
  result: DesignResponse | null
  rerendering: boolean
  rerenderError: string | null
  onRerender: (values: Record<string, number>) => void
}) {
  return (
    <aside className="kc-col-right">
      <ParametersCard
        result={result}
        rerendering={rerendering}
        rerenderError={rerenderError}
        onRerender={onRerender}
      />
      <ReadinessCard result={result} />
      <PrintabilityCard result={result} />
      <ExportPanel result={result} />
    </aside>
  )
}
