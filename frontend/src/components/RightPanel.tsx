import { type CSSProperties, useEffect, useRef, useState } from 'react'
import type { DesignResponse, ParamSpec } from '../api'
import { gateLabel, gateTone, isFailureStatus } from '../designStatus'
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
  return (
    <div className="kc-prow">
      <div className="kc-plabel">
        <span>
          {spec.label}
          {spec.axis && <i className="kc-axis">{spec.axis}</i>}
        </span>
        <span className="kc-pval">
          {formatValue(value, spec)}
          {spec.unit && <i>{spec.unit}</i>}
        </span>
      </div>
      <input
        type="range"
        className="kc-range"
        name={spec.name}
        aria-label={spec.label}
        // Announce the unit too — the native value ("150") alone drops the "mm".
        aria-valuetext={`${formatValue(value, spec)}${spec.unit ? ` ${spec.unit}` : ''}`}
        min={spec.min}
        max={spec.max}
        step={spec.step}
        value={value}
        style={{ '--pct': `${pct}%` } as CSSProperties}
        onChange={(e) => onChange(spec.name, Number(e.target.value))}
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
          <p className="kc-muted-note kc-param-hint">
            This part was generated directly rather than from a parametric template, so it has no
            preset sliders — but you can still slice and download it, or describe a change to start
            a new version.
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

function PrintabilityCard({ result }: { result: DesignResponse | null }) {
  const report = result?.report
  return (
    <section className="kc-card">
      <h2 className="kc-card-title">Printability</h2>
      {report ? (
        <>
          <span className={`kc-status-badge kc-tone-${gateTone(report.gate_status)}`}>
            {gateLabel(report.gate_status)}
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
      <PrintabilityCard result={result} />
      <ExportPanel result={result} />
    </aside>
  )
}
