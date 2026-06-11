import { useCallback, useEffect, useState } from 'react'
import { getConnections, saveConnection, type ConnectionInfo } from '../api'
import { displayName } from './SendPanel'

// Stage 11 Slice 11.2 — the in-app Connections card (the Stage-10 gate's root UX finding:
// the send flow's management venue didn't exist). One row per REAL printer connection:
// address + serial fields, the AMS toggle for Bambu, and the secret's env var NAMED with a
// copy-able `setx` line — the secret itself never passes through this surface. The
// per-piece "what's missing" comes from the same server diagnosis the send picker shows.
export default function ConnectionsCard() {
  const [conns, setConns] = useState<ConnectionInfo[] | null>(null)
  const [failed, setFailed] = useState(false)
  // Per-connection field drafts; seeded from the server once, kept while typing.
  const [drafts, setDrafts] = useState<Record<string, { base_url: string; serial: string; use_ams: boolean }>>({})
  const [saveState, setSaveState] = useState<Record<string, 'idle' | 'saving' | 'saved' | 'error'>>({})

  const load = useCallback(() => {
    setFailed(false)
    getConnections()
      .then((r) => {
        const real = r.connections.filter((c) => !c.simulated)
        setConns(real)
        setDrafts((prev) => {
          const next = { ...prev }
          for (const c of real) {
            if (!next[c.name]) {
              next[c.name] = { base_url: c.base_url, serial: c.serial, use_ams: c.use_ams }
            }
          }
          return next
        })
      })
      .catch(() => setFailed(true))
  }, [])
  useEffect(() => load(), [load])

  // N-2 (slice-11.2 audit): the send flow points here — a silent disappearance on a
  // failed load would be a dead end. Say so, offer a retry.
  if (failed) {
    return (
      <section className="kc-set-card">
        <h2 className="kc-set-h">Printer connections</h2>
        <p className="kc-muted-note">
          Couldn’t load your printer connections just now.{' '}
          <button type="button" className="kc-link-btn" onClick={load}>Try again</button>
        </p>
      </section>
    )
  }
  if (conns === null || conns.length === 0) return null

  async function save(c: ConnectionInfo) {
    const d = drafts[c.name]
    if (!d) return
    setSaveState((s) => ({ ...s, [c.name]: 'saving' }))
    try {
      // M-1 (slice-11.2 audit): the HTTP-family connectors (OctoPrint/Moonraker/PrusaLink)
      // need a scheme on their address; a bare host/IP would save, read "Ready", then fail
      // at send time. Bambu takes a bare IP (its protocols aren't HTTP).
      let address = d.base_url.trim()
      if (c.type !== 'bambu' && address && !/^https?:\/\//i.test(address)) {
        address = `http://${address}`
      }
      const updates: { base_url?: string; serial?: string; use_ams?: boolean } = {
        base_url: address,
      }
      // N-4: serial + the AMS toggle are Bambu concepts — never persisted for other types.
      if (c.type === 'bambu') {
        updates.serial = d.serial
        updates.use_ams = d.use_ams
      }
      await saveConnection(c.name, updates)
      setSaveState((s) => ({ ...s, [c.name]: 'saved' }))
      load() // re-read the effective values + the configured/note verdicts
    } catch {
      setSaveState((s) => ({ ...s, [c.name]: 'error' }))
    }
  }

  function edit(name: string, field: 'base_url' | 'serial', value: string) {
    setDrafts((d) => ({ ...d, [name]: { ...d[name], [field]: value } }))
    setSaveState((s) => ({ ...s, [name]: 'idle' }))
  }

  return (
    <section className="kc-set-card">
      <h2 className="kc-set-h">Printer connections</h2>
      <p className="kc-set-sub">
        Send finished prints straight from KimCad. Fill in a printer’s address (and for
        Bambu, its serial); the access code or API key stays in an environment variable —
        named below — so it never sits in a settings file.
      </p>
      {conns.map((c) => {
        const d = drafts[c.name] ?? { base_url: c.base_url, serial: c.serial, use_ams: c.use_ams }
        const state = saveState[c.name] ?? 'idle'
        return (
          <div key={c.name} className="kc-conn-row">
            <div className="kc-conn-head">
              <span className="kc-conn-name">{displayName(c.name)}</span>
              <span className={`kc-set-badge${c.configured ? ' kc-set-badge-local' : ''}`}>
                {c.configured ? 'Ready' : 'Not set up yet'}
              </span>
            </div>
            {!c.configured && c.note && <p className="kc-muted-note">{c.note}</p>}
            <div className="kc-set-row">
              <label htmlFor={`conn-url-${c.name}`}>Printer address</label>
              <input
                id={`conn-url-${c.name}`}
                className="kc-text-input kc-mono"
                placeholder={c.type === 'bambu' ? 'e.g. 192.168.0.60' : 'e.g. http://octopi.local'}
                value={d.base_url}
                onChange={(e) => edit(c.name, 'base_url', e.target.value)}
              />
            </div>
            {c.type === 'bambu' && (
              <>
                <div className="kc-set-row">
                  <label htmlFor={`conn-serial-${c.name}`}>Serial number</label>
                  <input
                    id={`conn-serial-${c.name}`}
                    className="kc-text-input kc-mono"
                    placeholder="on the printer: Settings → Device"
                    value={d.serial}
                    onChange={(e) => edit(c.name, 'serial', e.target.value)}
                  />
                </div>
                <div className="kc-set-row">
                  <label htmlFor={`conn-ams-${c.name}`}>Feed from the AMS</label>
                  <button
                    id={`conn-ams-${c.name}`}
                    type="button"
                    className={`kc-switch${d.use_ams ? ' kc-switch-on' : ''}`}
                    role="switch"
                    aria-checked={d.use_ams ? 'true' : 'false'}
                    aria-label="Feed from the AMS (off = external spool)"
                    onClick={() => {
                      setDrafts((dd) => ({ ...dd, [c.name]: { ...d, use_ams: !d.use_ams } }))
                      setSaveState((s) => ({ ...s, [c.name]: 'idle' }))
                    }}
                  />
                </div>
              </>
            )}
            {c.api_key_env && (
              <p className="kc-muted-note">
                {c.type === 'bambu' ? 'Access code' : 'API key'}:{' '}
                {c.env_set ? 'set ✓' : 'not set —'} kept in the environment variable{' '}
                <code className="kc-mono">{c.api_key_env}</code>
                {!c.env_set && (
                  <>
                    . In a terminal:{' '}
                    <code className="kc-mono">setx {c.api_key_env} your-code-here</code>, then
                    restart KimCad.
                  </>
                )}
              </p>
            )}
            <div className="kc-conn-actions">
              <button
                type="button"
                className="kc-btn kc-btn-accent"
                onClick={() => save(c)}
                disabled={state === 'saving'}
              >
                {state === 'saving' ? 'Saving…' : 'Save'}
              </button>
              <span className="kc-set-savenote" role="status">
                {state === 'saved' ? 'Saved.' : state === 'error' ? 'Couldn’t save — try again.' : ''}
              </span>
            </div>
          </div>
        )
      })}
    </section>
  )
}
