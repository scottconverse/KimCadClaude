import { useEffect, useState } from 'react'
import { getConnectors, getConnectorStatus, type ConnectorStatusResponse } from '../api'
import { connectorLabel, connectorTone } from '../connectorStatus'

// Read-only readiness of the default printer connection, shown at the top of Export & print.
// The direct-print send UI itself is SendPanel (Stage 10), offered under a finished slice;
// here we just show whether the connection is ready, busy, offline, or simulated.
export default function ConnectorStatus() {
  const [name, setName] = useState<string | null>(null)
  const [status, setStatus] = useState<ConnectorStatusResponse | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    getConnectors()
      .then((c) => {
        if (cancelled) return
        setName(c.default)
        if (!c.default) return
        return getConnectorStatus(c.default).then((s) => {
          if (!cancelled) setStatus(s)
        })
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // No connector configured (or the list couldn't be read) → nothing to show, no error noise.
  if (failed || name === null) return null

  return (
    <div className="kc-connector">
      <span className={`kc-status-dot kc-tone-${connectorTone(status)}`} aria-hidden="true" />
      <span className="kc-connector-name">{name}</span>
      <span className="kc-connector-label" role="status">
        {connectorLabel(status)}
      </span>
    </div>
  )
}
