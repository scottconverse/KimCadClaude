import { useEffect, useState } from 'react'
import { getSettings, postSettings, type SettingsResponse } from '../api'
import { useUnits } from '../useUnits'

// Stage 8.5 Slice 6 — the in-app Settings screen.
// MS-1 ships the screen shell + the Printer & Material defaults and the Units toggle. Later
// micro-slices add the AI model status, the cloud opt-in, the experimental-generator toggle, the
// tools health, and About — each as another <section className="kc-set-card"> in this same screen.
//
// Printer/material persist server-side (~/.kimcad/settings.json via /api/settings) so they're the
// app-wide default. Units stay in the shared client store (useUnits) — toggling here re-renders the
// whole app (the Parameters card, the dims table) in lockstep, exactly like the in-workspace toggle.

type SaveNote = 'idle' | 'saving' | 'saved' | 'error'

export default function SettingsPanel() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveNote, setSaveNote] = useState<SaveNote>('idle')
  const { unit, setUnit } = useUnits()

  useEffect(() => {
    let cancelled = false
    getSettings()
      .then((s) => { if (!cancelled) setSettings(s) })
      .catch(() => { if (!cancelled) setLoadError('Couldn’t load your settings.') })
    return () => { cancelled = true }
  }, [])

  async function change(updates: { default_printer?: string; default_material?: string }) {
    setSaveNote('saving')
    try {
      const next = await postSettings(updates)
      setSettings(next)
      // The server tells us honestly whether the choice persisted (saved:false if the local store
      // couldn't be written) so we never claim "Saved" when it didn't stick.
      setSaveNote(next.saved === false ? 'error' : 'saved')
    } catch {
      setSaveNote('error')
    }
  }

  return (
    <main className="kc-settings">
      <div className="kc-settings-head">
        <h1 className="kc-settings-title">Settings</h1>
        {saveNote === 'saving' && (
          <span className="kc-settings-note" role="status" aria-live="polite">Saving…</span>
        )}
        {saveNote === 'saved' && (
          <span className="kc-settings-note kc-settings-note-ok" role="status" aria-live="polite">
            <span className="kc-savedot" aria-hidden="true" /> Saved
          </span>
        )}
        {saveNote === 'error' && (
          <span className="kc-settings-note kc-settings-note-err" role="status" aria-live="polite">
            Couldn’t save — your choice didn’t stick
          </span>
        )}
      </div>

      {loadError ? (
        <p className="kc-muted-note kc-settings-empty" role="alert">{loadError}</p>
      ) : !settings ? (
        <p className="kc-muted-note kc-settings-empty">Loading your settings…</p>
      ) : (
        <div className="kc-settings-body">
          {/* Printer & material — the app-wide defaults new designs use. */}
          <section className="kc-set-card">
            <h2 className="kc-set-h">Printer &amp; material</h2>
            <p className="kc-set-sub">The default printer and material new designs are checked against.</p>
            <div className="kc-set-row">
              <label htmlFor="set-printer">Default printer</label>
              <select
                id="set-printer"
                className="kc-set-select"
                value={settings.default_printer ?? ''}
                onChange={(e) => change({ default_printer: e.target.value })}
              >
                {settings.printers.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.name}{p.sliceable ? '' : ' — no slicer profile yet'}
                  </option>
                ))}
              </select>
            </div>
            <div className="kc-set-row">
              <label htmlFor="set-material">Default material</label>
              <select
                id="set-material"
                className="kc-set-select"
                value={settings.default_material ?? ''}
                onChange={(e) => change({ default_material: e.target.value })}
              >
                {settings.materials.map((m) => (
                  <option key={m.key} value={m.key}>{m.name}</option>
                ))}
              </select>
            </div>
          </section>

          {/* Units — the shared display preference (mm / inch). */}
          <section className="kc-set-card">
            <h2 className="kc-set-h">Units</h2>
            <p className="kc-set-sub">How dimensions are shown everywhere — the sliders, the size, the printability table.</p>
            <div className="kc-set-row">
              <span id="set-units-label">Display units</span>
              <div className="kc-unit-toggle" role="group" aria-labelledby="set-units-label">
                <button
                  type="button"
                  className={`kc-unit-btn${unit === 'mm' ? ' kc-unit-btn-active' : ''}`}
                  onClick={() => setUnit('mm')}
                  aria-pressed={unit === 'mm'}
                >
                  mm
                </button>
                <button
                  type="button"
                  className={`kc-unit-btn${unit === 'in' ? ' kc-unit-btn-active' : ''}`}
                  onClick={() => setUnit('in')}
                  aria-pressed={unit === 'in'}
                >
                  in
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
    </main>
  )
}
