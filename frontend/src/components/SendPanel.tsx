import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getConnectors,
  getConnectorStatus,
  sendDesign,
  type ConnectorStatusResponse,
  type ConnectorsResponse,
  type SendResponse,
} from '../api'
import { connectorLabel, connectorTone } from '../connectorStatus'
import ConfirmDialog from './ConfirmDialog'

// Stage 10 Slice 10.2 — direct print from the app. Appears only once a print file exists
// (under the sliced result). Honest throughout: a simulated (loopback/no-hardware) connection
// is labeled a test connection and its send is narrated as a test, never as a real print; an
// unconfigured real connector is offered disabled with the reason; and a failed send is a
// soft, typed outcome with a next step — the download above remains the fallback. The confirm
// dialog here IS the user's explicit start: the POST is the confirmation (the server treats it
// as such and re-checks the gate verdict server-side) — so the send can only ever fire from
// the dialog's confirm action, never from merely opening this panel.
// UX-1004 (stage-10 gate): connection names come from config KEYS ("bambu_p2s") — present
// them in the product's register ("Bambu P2S") instead of raw snake_case one dropdown below
// the properly-named "Bambu Lab P2S" printer profile. Purely cosmetic: the VALUE sent to
// the server stays the exact config key.
export function displayName(key: string): string {
  return key
    .split('_')
    .map((w) => (/\d/.test(w) || w.length <= 2 ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1)))
    .join(' ')
}

export default function SendPanel({ designId }: { designId: number | null }) {
  const [conns, setConns] = useState<ConnectorsResponse | null>(null)
  const [chosen, setChosen] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<SendResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState<ConnectorStatusResponse | null>(null)
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Generation counter: a new send (or unmount) bumps it, and any in-flight status request
  // from an older chain drops its result instead of rescheduling — so re-slicing (which
  // unmounts this panel) can't leak background polling, and a superseding send can't have
  // the OLD connector's status painted under the NEW job's banner.
  const pollGen = useRef(0)

  useEffect(() => {
    let cancelled = false
    getConnectors()
      .then((c) => {
        if (cancelled) return
        setConns(c)
        // Prefer the configured default, then the first CONFIGURED connector (the server's
        // `default` is config-order and may be unconfigured); if nothing is configured, still
        // select the first entry so the picker isn't blank — the button stays disabled and
        // the note below says why.
        const usable = c.connectors.filter((x) => x.configured)
        const def = c.default && usable.some((x) => x.name === c.default) ? c.default : usable[0]?.name
        setChosen(def ?? c.connectors[0]?.name ?? '')
      })
      .catch(() => {
        /* no connector list — the panel stays hidden; downloading still works */
      })
    return () => {
      cancelled = true
    }
  }, [])

  // After a real send, follow the printer's live status until it settles — polled, bounded,
  // generation-guarded, and stopped on unmount so an abandoned workspace doesn't poll forever.
  const stopPoll = useCallback(() => {
    pollGen.current += 1 // invalidate any in-flight chain, not just the scheduled timer
    if (pollTimer.current) clearTimeout(pollTimer.current)
    pollTimer.current = null
  }, [])
  useEffect(() => stopPoll, [stopPoll])

  const pollStatus = useCallback((name: string, remaining: number, gen: number) => {
    getConnectorStatus(name)
      .then((s) => {
        if (pollGen.current !== gen) return // superseded or unmounted — drop silently
        setLive(s)
        const stillGoing = s.state === 'printing' || s.state === 'paused' || s.reason === 'busy'
        if (stillGoing && remaining > 0) {
          pollTimer.current = setTimeout(() => pollStatus(name, remaining - 1, gen), 5000)
        }
      })
      .catch(() => {
        // ENG-1003 (stage-10 gate): one missed poll must not kill the live follow forever
        // (a stale "printing" would stand for good). Keep the chain alive on the same
        // bounded budget; the last known status shows meanwhile.
        if (pollGen.current !== gen) return
        if (remaining > 0) {
          pollTimer.current = setTimeout(() => pollStatus(name, remaining - 1, gen), 5000)
        }
      })
  }, [])

  // UX-1001 (stage-10 gate): when the chosen connection isn't set up, fetch ITS status —
  // the server's note names the exact missing piece (IP vs serial vs access code vs the
  // optional package), which beats a generic pointer at a venue.
  const [setupNote, setSetupNote] = useState<string | null>(null)
  const entryForNote = conns?.connectors.find((c) => c.name === chosen) ?? null
  const needsNote = !!entryForNote && !entryForNote.configured
  useEffect(() => {
    if (!needsNote || !chosen) {
      setSetupNote(null)
      return
    }
    let cancelled = false
    getConnectorStatus(chosen)
      .then((s) => {
        if (!cancelled) setSetupNote(s.note || null)
      })
      .catch(() => {
        if (!cancelled) setSetupNote(null)
      })
    return () => {
      cancelled = true
    }
  }, [chosen, needsNote])

  const entry = conns?.connectors.find((c) => c.name === chosen) ?? null
  // Nothing to offer: no design id, no connectors at all, or none even selectable.
  if (designId == null || !conns || conns.connectors.length === 0) return null

  async function doSend() {
    setConfirming(false)
    if (designId == null || !chosen) return
    setSending(true)
    setError(null)
    setResult(null)
    setLive(null)
    stopPoll()
    try {
      const r = await sendDesign(designId, chosen)
      setResult(r)
      if (r.sent && !r.simulated) pollStatus(chosen, 120, pollGen.current) // follow a REAL job (~10 min cap)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Couldn’t reach the printer connection.')
    } finally {
      setSending(false)
    }
  }

  // UX-1001 (stage-10 gate) closed for real at Slice 11.2: the venue these hints name —
  // Settings → Printer connections — EXISTS now (ConnectionsCard).
  const reasonHint: Record<string, string> = {
    offline: 'Check the printer is powered on and reachable on your network, then try again.',
    auth: 'The printer rejected the key or access code — re-check it on the printer; Settings → Printer connections names the environment variable to update.',
    config: 'Finish setting this connection up in Settings → Printer connections.',
    busy: 'The printer is busy with another job — try again when it’s free.',
    gate_failed: '', // the server’s note already says everything
  }

  return (
    <div className="kc-send-panel">
      <h3 className="kc-send-title">Send to printer</h3>
      <div className="kc-send-row">
        <label className="kc-field kc-send-field">
          <span>Printer connection</span>
          <select value={chosen} onChange={(e) => setChosen(e.target.value)} disabled={sending}>
            {conns.connectors.map((c) => (
              <option key={c.name} value={c.name} disabled={!c.configured}>
                {displayName(c.name)}
                {c.simulated ? ' (test connection — no real printer)' : ''}
                {!c.configured ? ' (not set up yet)' : ''}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="kc-btn kc-btn-accent kc-send-btn"
          onClick={() => setConfirming(true)}
          disabled={sending || !entry || !entry.configured}
        >
          {sending ? 'Sending…' : entry?.simulated ? 'Send test job' : 'Send to printer'}
        </button>
      </div>
      {entry?.simulated && (
        <p className="kc-muted-note">
          This is a built-in test connection — it proves the send path without driving any
          hardware. To print directly, set up a real printer in Settings → Printer
          connections.
        </p>
      )}
      {/* UX-1001: the chosen-but-unconfigured connection's EXACT missing piece, straight
          from the server (the per-piece diagnosis was previously CLI/API-only). */}
      {needsNote && setupNote && (
        <p className="kc-muted-note">
          {setupNote} Set it up in Settings → Printer connections.
        </p>
      )}
      {/* Every connection unconfigured: the disabled button needs its "why" visible, not
          hidden inside the closed dropdown. */}
      {!conns.connectors.some((c) => c.configured) && (
        <p className="kc-muted-note">
          None of these printer connections is set up yet — Settings → Printer connections
          is where they’re filled in. Downloading the print file above always works.
        </p>
      )}

      {confirming && entry && (
        <ConfirmDialog
          message={
            entry.simulated
              ? `Send a test job to “${displayName(entry.name)}”? No real printer will run — this only exercises the send path.`
              : `Start this print on “${displayName(entry.name)}”? KimCad sends the print file and the printer begins the job.`
          }
          confirmLabel={entry.simulated ? 'Send test job' : 'Start the print'}
          onConfirm={doSend}
          onCancel={() => setConfirming(false)}
        />
      )}

      {error !== null && (
        <p className="kc-muted-note kc-export-error" role="status">
          {error}
        </p>
      )}

      {result && !result.sent && (
        <p className="kc-muted-note kc-export-error" role="status">
          {result.note || 'The job wasn’t sent.'}
          {result.reason && reasonHint[result.reason] ? ` ${reasonHint[result.reason]}` : ''}{' '}
          Your print file is still downloadable above.
        </p>
      )}

      {result && result.sent && (
        <div className="kc-send-result" role="status">
          <p className="kc-send-ok">
            {result.simulated
              ? `Test job accepted by “${displayName(result.connector ?? chosen)}” — the send path works. No hardware ran.`
              : `Job sent to “${displayName(result.connector ?? chosen)}”${result.job_id ? ` (job ${result.job_id})` : ''} — the printer is starting.`}
          </p>
          {!result.simulated && (
            <p className="kc-send-live">
              {/* UX-1006 (stage-10 gate): right after OUR send, "printing" is the user's
                  own job — narrate it as progress, never as an amber "Busy" blocker. */}
              {live?.state === 'printing' ? (
                <>
                  <span className="kc-status-dot kc-tone-ok" aria-hidden="true" /> Printing —
                  your job is running.
                </>
              ) : (
                <>
                  <span className={`kc-status-dot kc-tone-${connectorTone(live)}`} aria-hidden="true" />{' '}
                  {connectorLabel(live)}
                </>
              )}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
