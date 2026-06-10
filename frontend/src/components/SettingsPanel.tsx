import { useCallback, useEffect, useState } from 'react'
import {
  getHealth,
  getModelStatus,
  getSettings,
  postSettings,
  type HealthStatus,
  type ModelStatus,
  type SettingsResponse,
} from '../api'
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

// The model-status dot tone + label. gemma4:e4b is THE model — this is a health readout, never a
// menu of alternatives (trust rule 1).
function modelTone(m: ModelStatus): 'ok' | 'warn' {
  if (m.backend === 'cloud') return 'ok'
  return m.running && m.model_present ? 'ok' : 'warn'
}
function modelLabel(m: ModelStatus): string {
  if (m.backend === 'cloud') return 'Cloud'
  if (!m.running) return 'Not running'
  if (!m.model_present) return 'Model not pulled'
  return 'Running'
}

export default function SettingsPanel() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveNote, setSaveNote] = useState<SaveNote>('idle')
  const { unit, setUnit } = useUnits()

  // The model status loads independently of the printer/material settings: the Ollama probe can
  // take a moment, so it shouldn't hold up the rest of the screen.
  const [model, setModel] = useState<ModelStatus | null>(null)
  const [modelState, setModelState] = useState<'checking' | 'ready' | 'error'>('checking')

  // Cloud (OpenRouter) opt-in drafts (MS-3). The model field is seeded once from settings on load
  // (not re-seeded on every save, so in-progress typing survives an unrelated change). The key is
  // entered into `keyDraft`; once saved it shows masked, with Replace to enter a new one.
  const [modelDraft, setModelDraft] = useState('')
  const [keyDraft, setKeyDraft] = useState('')
  const [replacingKey, setReplacingKey] = useState(false)

  // MS-5: tool + app health (loads independently), and the reset-to-defaults confirm.
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [healthError, setHealthError] = useState(false)
  const [confirmingReset, setConfirmingReset] = useState(false)

  const checkModel = useCallback(() => {
    setModelState('checking')
    getModelStatus()
      .then((m) => { setModel(m); setModelState('ready') })
      .catch(() => setModelState('error'))
  }, [])

  useEffect(() => {
    let cancelled = false
    getSettings()
      .then((s) => {
        if (cancelled) return
        setSettings(s)
        setModelDraft(s.cloud_model ?? '')
      })
      .catch(() => { if (!cancelled) setLoadError('Couldn’t load your settings.') })
    return () => { cancelled = true }
  }, [])

  useEffect(() => { checkModel() }, [checkModel])

  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((h) => { if (!cancelled) setHealth(h) })
      .catch(() => { if (!cancelled) setHealthError(true) })
    return () => { cancelled = true }
  }, [])

  async function change(updates: Parameters<typeof postSettings>[0]) {
    setSaveNote('saving')
    try {
      const next = await postSettings(updates)
      setSettings(next)
      // The server tells us honestly whether the choice persisted (saved:false if the local store
      // couldn't be written) so we never claim "Saved" when it didn't stick.
      setSaveNote(next.saved === false ? 'error' : 'saved')
      // A cloud change flips which model handles requests — re-check so the AI section reflects it.
      if ('cloud_enabled' in updates || 'cloud_model' in updates || 'openrouter_api_key' in updates) {
        checkModel()
      }
    } catch {
      setSaveNote('error')
    }
  }

  async function saveKey() {
    const k = keyDraft.trim()
    if (!k) return
    await change({ openrouter_api_key: k })
    setReplacingKey(false)
    setKeyDraft('')
  }

  // DOC-D-001 (stage-BCD gate): the guide promises a way to delete the stored key — this is
  // it. Removes the key from the credential store (or the file fallback) via the same
  // settings path; cloud stays opt-in-able again afterwards.
  async function removeKey() {
    await change({ openrouter_api_key: null })
    setReplacingKey(false)
    setKeyDraft('')
  }

  function saveModel() {
    const m = modelDraft.trim()
    if (m === (settings?.cloud_model ?? '')) return // no change — don't fire a redundant save
    void change({ cloud_model: m })
  }

  async function resetAll() {
    setConfirmingReset(false)
    setKeyDraft('')
    setReplacingKey(false)
    setModelDraft('')
    setUnit('mm')
    // A full reset clears every saved override server-side (pristine), not a set-each-to-false.
    await change({ reset: true })
  }

  return (
    <main id="kimcad-main" className="kc-settings">
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

          {/* AI model (Surface A) — gemma4:e4b shown as THE model with its health. No menu of
              alternatives; the manual backend override stays CLI-only (trust rule 1). */}
          <section className="kc-set-card">
            <div className="kc-set-cardhead">
              <h2 className="kc-set-h">AI model</h2>
              {modelState === 'ready' && model && (
                <span className={`kc-set-badge kc-set-badge-${model.backend}`}>
                  {model.backend === 'local' ? 'Local' : 'Cloud'}
                </span>
              )}
              <span className="kc-set-grow" />
              {modelState === 'checking' ? (
                <span className="kc-model-stat" role="status">
                  <span className="kc-spin-sm" aria-hidden="true" /> Checking…
                </span>
              ) : modelState === 'error' ? (
                <span className="kc-model-stat kc-model-stat-warn" role="status">Couldn’t check</span>
              ) : model ? (
                <span className={`kc-model-stat kc-model-stat-${modelTone(model)}`} role="status">
                  <span className="kc-statdot" aria-hidden="true" /> {modelLabel(model)}
                </span>
              ) : null}
            </div>
            {/* UX-001: the description MUST track the live backend — when cloud is on, the model runs
                off-machine, so the on-device privacy copy would be a flat contradiction of the
                product's core promise. Branch on the same `model` status object the badge uses. */}
            {model?.backend === 'cloud' ? (
              <p className="kc-set-sub">
                <code className="kc-mono">{model?.model ?? 'your cloud model'}</code> — your chosen
                cloud model via OpenRouter. It runs on OpenRouter’s servers, not your machine: your
                prompt is sent to the cloud while this is on. Turn Cloud acceleration off to keep
                everything on-device.
              </p>
            ) : (
              <p className="kc-set-sub">
                {/* UX-105 (stage-BCD gate): the friendly name leads; the slug is the detail. */}
                KimCad’s local AI (<code className="kc-mono">{model?.model ?? 'gemma4:e4b'}</code>).
                Runs on your machine, on your CPU. No internet required; nothing leaves your computer.
              </p>
            )}
            {/* Slice 10.4 (Stage 9 watchlist #3): the SECOND local model — the photo & sketch
                reader — gets its own row, so a user diagnosing an image failure finds the
                answer here, not just in the moment the upload fails. Absent vision fields
                (e.g. a cloud chat backend can't probe it) mean unknown — say nothing. */}
            {model?.backend === 'local' && model.vision_present !== undefined && (
              <p className="kc-set-sub kc-set-vision-row">
                Photo &amp; sketch reader (<code className="kc-mono">{model.vision_model}</code>):{' '}
                {model.vision_present ? (
                  'downloaded.'
                ) : (
                  <>
                    not downloaded — photos and sketches won’t work yet. Run{' '}
                    <code className="kc-mono">ollama pull {model.vision_model}</code> (or use the
                    setup wizard’s download), then{' '}
                    <button
                      type="button"
                      className="kc-link-btn"
                      aria-disabled={modelState === 'checking' || undefined}
                      onClick={() => {
                        if (modelState !== 'checking') checkModel()
                      }}
                    >
                      {modelState === 'checking' ? 'checking…' : 'check again'}
                    </button>.
                  </>
                )}
              </p>
            )}
            {/* A concrete next action whenever it isn't simply running (no dead-end). */}
            {modelState === 'ready' && model?.backend === 'local' && !model.running && (
              <p className="kc-model-action">
                Ollama isn’t running. Start it, then{' '}
                <button type="button" className="kc-link-btn" onClick={checkModel}>check again</button>.
              </p>
            )}
            {modelState === 'ready' && model?.backend === 'local' && model.running && !model.model_present && (
              <p className="kc-model-action">
                The model isn’t pulled yet. Pull <code className="kc-mono">{model.model}</code> in
                Ollama, then{' '}
                <button type="button" className="kc-link-btn" onClick={checkModel}>check again</button>.
              </p>
            )}
            {(modelState === 'error' || (modelState === 'ready' && model?.running && model?.model_present)) && (
              <button type="button" className="kc-link-btn kc-model-refresh" onClick={checkModel}>
                Refresh
              </button>
            )}
          </section>

          {/* Cloud acceleration (Surface B) — opt-in, OFF by default. Per spec §7.3, KimCad does NOT
              hardwire a cloud vendor: OpenRouter is the router and the USER picks the model. The key
              is saved locally and shown masked (last 5) on return. */}
          <section className="kc-set-card">
            <div className="kc-set-cardhead">
              <h2 className="kc-set-h">Cloud acceleration</h2>
              <span className={`kc-set-badge${settings.cloud_enabled ? ' kc-set-badge-cloud' : ''}`}>
                {settings.cloud_enabled ? 'On' : 'Off'}
              </span>
              <span className="kc-set-grow" />
              <button
                type="button"
                className={`kc-switch${settings.cloud_enabled ? ' kc-switch-on' : ''}`}
                role="switch"
                aria-checked={settings.cloud_enabled ? 'true' : 'false'}
                aria-label="Use a cloud model"
                onClick={() => change({ cloud_enabled: !settings.cloud_enabled })}
              />
            </div>
            <p className="kc-set-sub">
              Local always works. Turn this on to send a design prompt to a cloud model — your choice,
              via OpenRouter — for a hard request.
            </p>
            <div className="kc-set-callout kc-set-callout-privacy">
              <b>This sends your prompt off your machine.</b> Off by default — KimCad stays on your
              computer until you choose this.
            </div>

            {settings.cloud_enabled && (
              <div className="kc-cloud-config">
                <div className="kc-set-field">
                  <label htmlFor="cloud-key">OpenRouter API key</label>
                  {settings.has_cloud_key && !replacingKey ? (
                    <div className="kc-set-fieldrow">
                      <input
                        id="cloud-key"
                        className="kc-set-input kc-mono"
                        value={settings.cloud_key_masked ?? ''}
                        readOnly
                        aria-label="Saved OpenRouter key (masked)"
                      />
                      <button
                        type="button"
                        className="kc-btn-sm"
                        onClick={() => { setReplacingKey(true); setKeyDraft('') }}
                      >
                        Replace
                      </button>
                      <button type="button" className="kc-btn-sm" onClick={removeKey}>
                        Remove
                      </button>
                    </div>
                  ) : (
                    <div className="kc-set-fieldrow">
                      <input
                        id="cloud-key"
                        className="kc-set-input kc-mono"
                        type="password"
                        value={keyDraft}
                        placeholder="Paste your OpenRouter key"
                        aria-label="OpenRouter API key"
                        autoComplete="off"
                        spellCheck={false}
                        onChange={(e) => setKeyDraft(e.target.value)}
                      />
                      <button
                        type="button"
                        className="kc-btn-sm kc-btn-accent-sm"
                        disabled={!keyDraft.trim()}
                        onClick={saveKey}
                      >
                        Save
                      </button>
                    </div>
                  )}
                  <a
                    className="kc-link-btn kc-set-link"
                    href="https://openrouter.ai/keys"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Get a free OpenRouter key →
                  </a>
                  {/* ENG-001: disclose where the key lives at rest, honestly per backend. */}
                  <p className="kc-muted-note kc-key-storage-note">
                    {settings.key_storage === 'file'
                      ? 'Your key is kept in a settings file on this computer (the secure ' +
                        'credential store isn’t available here). Anyone who can read your ' +
                        'files could read it.'
                      : 'Your key is kept in this computer’s secure credential store ' +
                        '(Windows Credential Manager) — never in a plain file.'}
                  </p>
                </div>

                <div className="kc-set-field">
                  <label htmlFor="cloud-model">Model</label>
                  <input
                    id="cloud-model"
                    className="kc-set-input kc-mono"
                    value={modelDraft}
                    placeholder="a model slug from openrouter.ai/models"
                    aria-label="OpenRouter model"
                    onChange={(e) => setModelDraft(e.target.value)}
                    onBlur={saveModel}
                    onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }}
                  />
                  <a
                    className="kc-link-btn kc-set-link"
                    href="https://openrouter.ai/models"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Browse models on OpenRouter →
                  </a>
                  <p className="kc-set-fallback-note">
                    If a model isn’t reachable, KimCad falls back to your local model — a design
                    never fails just because a cloud slug is wrong.
                  </p>
                </div>
              </div>
            )}
          </section>

          {/* Experimental raw-codegen generator (Surface C) — OFF by default, untrusted. */}
          <section className="kc-set-card">
            <div className="kc-set-cardhead">
              <h2 className="kc-set-h">Experimental: direct shape generator</h2>
              <span className="kc-set-badge kc-set-badge-exp">Experimental · Untrusted</span>
              <span className="kc-set-grow" />
              <button
                type="button"
                className={`kc-switch${settings.experimental_enabled ? ' kc-switch-on' : ''}`}
                role="switch"
                aria-checked={settings.experimental_enabled ? 'true' : 'false'}
                aria-label="Enable the experimental shape generator"
                onClick={() => change({ experimental_enabled: !settings.experimental_enabled })}
              />
            </div>
            <p className="kc-set-sub">
              Lets the AI write the 3D shape directly when no template fits. Off by default. Runs in a
              locked sandbox; never skips the printability check; results can be rough.
            </p>
            <div className="kc-set-callout kc-set-callout-warn">
              {settings.experimental_enabled
                ? 'On — a part with no template generates directly (it still has to pass the check).'
                : 'Off — a part with no template offers the generator rather than running it.'}
            </div>
          </section>

          {/* Tools health (MS-5) — the bundled engines. */}
          <section className="kc-set-card">
            <h2 className="kc-set-h">Tools</h2>
            <p className="kc-set-sub">The bundled engines KimCad uses to build and slice your parts.</p>
            {(['openscad', 'orcaslicer'] as const).map((tool) => (
              <div className="kc-set-row" key={tool}>
                <span>{tool === 'openscad' ? 'OpenSCAD' : 'OrcaSlicer'}</span>
                <span
                  className={`kc-tool-stat kc-tool-stat-${
                    health ? (health[tool] ? 'ok' : 'missing') : healthError ? 'missing' : 'unknown'
                  }`}
                  role="status"
                >
                  {health
                    ? health[tool] ? 'Installed' : 'Not found'
                    : healthError ? 'Couldn’t check' : 'Checking…'}
                </span>
              </div>
            ))}
          </section>

          {/* About + reset (MS-5). */}
          <section className="kc-set-card">
            <h2 className="kc-set-h">About</h2>
            <div className="kc-set-row">
              <span>KimCad</span>
              <span className="muted kc-set-about">
                {health ? `v${health.version} · ` : ''}open-source (Apache-2.0)
              </span>
            </div>
            <div className="kc-set-row">
              <span>Reset all settings to defaults</span>
              {confirmingReset ? (
                <span className="kc-reset-confirm">
                  <button type="button" className="kc-btn-sm kc-btn-danger-sm" onClick={resetAll}>
                    Reset everything
                  </button>
                  <button type="button" className="kc-btn-sm" onClick={() => setConfirmingReset(false)}>
                    Cancel
                  </button>
                </span>
              ) : (
                <button type="button" className="kc-btn-sm" onClick={() => setConfirmingReset(true)}>
                  Reset…
                </button>
              )}
            </div>
          </section>
        </div>
      )}
    </main>
  )
}
