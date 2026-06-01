import type { DesignResponse } from '../api'
import { gateLabel, gateTone } from '../designStatus'

// Right column — parameters + printability, rendered from the design result.
// Parameters are READ-ONLY in Stage 4 (live sliders are Stage 5). The printability card shows
// the gate verdict, the target-vs-actual dimensions, and any findings.

function ParametersCard({ result }: { result: DesignResponse | null }) {
  const plan = result?.plan
  return (
    <section className="kc-card">
      <h2 className="kc-card-title">Parameters</h2>
      {plan ? (
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
            These are read-only for now — live sliders arrive with the template engine.
          </p>
        </>
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
      ) : (
        <p className="kc-muted-note">
          The printability check — dimensions, wall thickness, build-volume fit — appears here
          after a part is designed.
        </p>
      )}
    </section>
  )
}

export default function RightPanel({ result }: { result: DesignResponse | null }) {
  return (
    <aside className="kc-col-right">
      <ParametersCard result={result} />
      <PrintabilityCard result={result} />
    </aside>
  )
}
