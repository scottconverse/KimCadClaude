import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getModelPullProgress,
  getModelStatus,
  getSettings,
  postSettings,
  startModelPull,
  type ModelPullSnapshot,
  type ModelStatus,
  type SettingsResponse,
} from '../api'

// Stage 8.5 Slice 9 MS-4 — the first-run setup walkthrough (spec §5.1; built to
// docs/design/prototype/jsx/wizard.jsx). A 5-step guided setup: Welcome → Your AI model →
// Your printer → Direct printing (optional) → Ready. It is SELECTION + persistence wired to the
// existing endpoints (/api/settings, /api/model-status) — there is no model download and no
// installer/SmartScreen step here; those belong to the Stage-11 bundled installer.
//
// Two deliberate departures from the (stale) prototype: the model is gemma4:e4b shown as THE
// model with its health — NOT a qwen-vs-gemma choice (trust rule 1: never offer alternatives) —
// and the "direct printing" step is an honest download-vs-later choice rather than a fake
// connect-and-test form (the connector setup UI lands later).

const STEPS = ['Welcome', 'Your AI model', 'Your printer', 'Direct printing', 'Ready'] as const

function modelLabel(m: ModelStatus): string {
  if (m.backend === 'cloud') return 'Cloud'
  if (!m.running) return 'Ollama isn’t running'
  if (!m.model_present) return 'Model not pulled yet'
  // UX-1005 (stage-10 gate): a bare "Ready" beside a card offering the vision download
  // claimed more than is true — designing works, the image on-ramps don't yet.
  if (m.vision_present === false) return 'Ready — words only'
  return 'Ready'
}
function modelTone(m: ModelStatus): 'ok' | 'warn' {
  if (m.backend === 'cloud') return 'ok'
  return m.running && m.model_present ? 'ok' : 'warn'
}

export default function FirstRunWizard({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0)
  const [settings, setSettings] = useState<SettingsResponse | null>(null)
  const [model, setModel] = useState<ModelStatus | null>(null)
  const [modelState, setModelState] = useState<'checking' | 'ready' | 'error'>('checking')
  // Cloud opt-in is gathered here and persisted at finish (so a half-entered key never sticks).
  const [cloudOn, setCloudOn] = useState(false)
  const [keyDraft, setKeyDraft] = useState('')
  const [cloudModelDraft, setCloudModelDraft] = useState('')
  // Direct-printing choice (honest: download now, or connect a printer later in Settings).
  const [directLater, setDirectLater] = useState(false)
  const [settingsError, setSettingsError] = useState(false)
  const dialogRef = useRef<HTMLDivElement>(null)

  const checkModel = useCallback(() => {
    setModelState('checking')
    getModelStatus()
      .then((m) => {
        setModel(m)
        setModelState('ready')
      })
      .catch(() => setModelState('error'))
  }, [])

  useEffect(() => {
    let cancelled = false
    getSettings()
      .then((s) => {
        if (!cancelled) setSettings(s)
      })
      .catch(() => {
        // A settings load failure shouldn't trap the user in the wizard — the steps still work and
        // Settings is reachable later. The printer step swaps to an honest "couldn't load" message.
        if (!cancelled) setSettingsError(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => checkModel(), [checkModel])

  // Slice 10.4 — the in-app model download. POST starts whatever's missing (the model list
  // is fixed server-side); we poll progress once a second until the job ends, then re-probe
  // the model status so "Ready" is a measured claim. The poll dies with the wizard.
  const [pull, setPull] = useState<ModelPullSnapshot | null>(null)
  const pullTimer = useRef<number | null>(null)
  // ENG-001 (slice-10.4 audit): if the wizard unmounts between the Download click and the
  // POST resolving, the .then would otherwise install the interval AFTER cleanup ran —
  // a poll that never dies. The disposed flag closes that window.
  const disposedRef = useRef(false)
  const stopPolling = useCallback(() => {
    if (pullTimer.current !== null) {
      window.clearInterval(pullTimer.current)
      pullTimer.current = null
    }
  }, [])
  useEffect(
    () => () => {
      disposedRef.current = true
      stopPolling()
    },
    [stopPolling],
  )

  const beginPull = useCallback(() => {
    setPull({ running: true, models: {} })
    startModelPull()
      .then((snap) => {
        if (disposedRef.current) return
        setPull(snap)
        if (snap.status !== 'ok' || !snap.running) return // typed refusal or nothing missing
        stopPolling()
        pullTimer.current = window.setInterval(() => {
          getModelPullProgress()
            .then((p) => {
              setPull((prev) => ({ ...prev, ...p }))
              if (!p.running) {
                stopPolling()
                checkModel() // re-probe: "Ready" must be measured, not assumed
              }
            })
            .catch(() => {
              /* one missed poll isn't a failure; the next tick retries */
            })
        }, 1000)
      })
      .catch(() => {
        if (disposedRef.current) return
        setPull({ status: 'ok', running: false, error: 'Couldn’t start the download — check that Ollama is running, then try again.' })
      })
  }, [checkModel, stopPolling])

  const pullActive = pull?.running === true
  // A11Y-001 (slice-10.4 audit): the live announcement is COARSE — per-model status words
  // only, never the percent — so its text changes a handful of times across a multi-GB
  // download instead of every second. The visible rows carry the percent, un-live.
  const pullAnnouncement = (() => {
    if (!pull) return ''
    if (pull.error) return pull.error
    const entries = Object.entries(pull.models ?? {})
    if (entries.length === 0) return pullActive ? 'Starting the download…' : ''
    return entries
      .map(([n, s]) =>
        s.status === 'done'
          ? `${n} downloaded`
          : s.status === 'error'
            ? `${n} failed`
            : s.status === 'pulling'
              ? `downloading ${n}`
              : `${n} waiting`,
      )
      .join('; ')
  })()

  // UX-002 (2026-06-09 audit): re-probe when the recap step opens, so "you're all set" is a
  // claim about NOW — the user may have started Ollama (or not) since step 1 checked.
  useEffect(() => {
    if (step === STEPS.length - 1) checkModel()
  }, [step, checkModel])

  // Move focus into the dialog on mount so keyboard users start inside it; Escape skips setup; and
  // Tab is trapped inside the dialog so keyboard/SR users can't tab out onto the (still-present)
  // page behind the modal — `aria-modal` alone is only a hint, not a focus boundary.
  useEffect(() => {
    dialogRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      const root = dialogRef.current
      if (!root) return
      const focusable = Array.from(
        root.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement
      if (e.shiftKey && (active === first || active === root)) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const next = () => setStep((s) => Math.min(STEPS.length - 1, s + 1))
  const back = () => setStep((s) => Math.max(0, s - 1))

  function pickPrinter(key: string) {
    setSettings((s) => (s ? { ...s, default_printer: key } : s))
    void postSettings({ default_printer: key }).catch(() => {
      /* best-effort; the choice is also re-settable in Settings. */
    })
  }

  // Persistence model: the printer choice persists the moment it's picked (pickPrinter); the cloud
  // opt-in persists only here, at finish. So "Skip setup" / Escape intentionally abandon an
  // unsaved cloud key (we never half-commit one), while a printer already picked stays — both are
  // re-settable in Settings.
  async function finish() {
    // Persist the cloud opt-in only if the user turned it on AND gave a key (a key without a model
    // still enables the opt-in; the model can be chosen later in Settings).
    if (cloudOn && keyDraft.trim()) {
      try {
        await postSettings({
          cloud_enabled: true,
          openrouter_api_key: keyDraft.trim(),
          ...(cloudModelDraft.trim() ? { cloud_model: cloudModelDraft.trim() } : {}),
        })
      } catch {
        /* a cloud-save failure shouldn't block finishing setup — local always works. */
      }
    }
    onClose()
  }

  const printers = settings?.printers ?? []
  const chosenPrinter = printers.find((p) => p.key === settings?.default_printer) ?? printers[0]
  const headingId = `kc-wiz-h-${step}`
  // UX-002: "ready" means the model is actually usable (cloud backends manage themselves).
  // Derived from the LAST KNOWN status — checkModel keeps `model` while a re-probe is in
  // flight, so the recap headline never flashes pessimistic mid-check; the quiet re-probe
  // updates it only if the truth changed. A never-probed model (null) reads as not-ready.
  const modelOk =
    model !== null && (model.backend === 'cloud' || (model.running && model.model_present))

  return (
    <div
      className="kc-wiz-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby={headingId}
      ref={dialogRef}
      tabIndex={-1}
    >
      <div className="kc-wiz">
        <aside className="kc-wiz-rail">
          <div className="kc-wiz-brand">
            Kim<b>Cad</b>
          </div>
          <ol className="kc-wiz-steps">
            {STEPS.map((s, i) => (
              <li
                key={s}
                className={`kc-wiz-step${i === step ? ' on' : ''}${i < step ? ' done' : ''}`}
                aria-current={i === step ? 'step' : undefined}
              >
                <span className="kc-wiz-num" aria-hidden="true">
                  {i < step ? '✓' : i + 1}
                </span>
                {s}
              </li>
            ))}
          </ol>
          <p className="kc-wiz-budget">Most first prints are ready in under 15 minutes.</p>
          <button type="button" className="kc-wiz-skip" onClick={onClose}>
            Skip setup
          </button>
        </aside>

        <div className="kc-wiz-body">
          <div className="kc-wiz-content">
            {step === 0 && (
              <>
                <h1 id={headingId} className="kc-wiz-h1">
                  Welcome to KimCad
                </h1>
                {/* UX-905 (stage-9 gate): the welcome names all three on-ramps — words, photo,
                    AND sketch — so the new path is discoverable from the first screen. */}
                <p className="kc-wiz-lede">
                  Describe a part in plain words — or start from a photo or a sketch — and get a
                  print-ready file in minutes. It runs on your computer; nothing leaves your machine
                  unless you choose to. Let’s get you set up.
                </p>
                <ul className="kc-wiz-bullets">
                  <li>Pick the AI model that turns your words into a design.</li>
                  <li>Choose the printer your parts are checked against.</li>
                  <li>Decide how you want to get your files.</li>
                </ul>
              </>
            )}

            {step === 1 && (
              <>
                <h1 id={headingId} className="kc-wiz-h1">
                  Your AI model
                </h1>
                <p className="kc-wiz-lede">
                  KimCad runs a small local model to turn your words into a validated design plan. It
                  works fully offline.
                </p>
                <div className="kc-wiz-modelcard">
                  <div className="kc-wiz-modelcard-top">
                    {/* UX-011: lead with the friendly name; the raw slug is a secondary detail. */}
                    <span className="kc-wiz-model-name">
                      KimCad local AI{' '}
                      <span className="kc-mono kc-wiz-model-slug">{model?.model ?? 'gemma4:e4b'}</span>
                    </span>
                    {modelState === 'checking' ? (
                      <span className="kc-wiz-model-stat" role="status">
                        <span className="kc-spin-sm" aria-hidden="true" /> Checking…
                      </span>
                    ) : modelState === 'error' ? (
                      <span className="kc-wiz-model-stat kc-wiz-model-warn" role="status">
                        Couldn’t check
                      </span>
                    ) : model ? (
                      <span
                        className={`kc-wiz-model-stat kc-wiz-model-${modelTone(model)}`}
                        role="status"
                      >
                        <span className="kc-statdot" aria-hidden="true" /> {modelLabel(model)}
                      </span>
                    ) : null}
                  </div>
                  {/* UX-908 (stage-9 gate): plain words — what the second download DOES, not
                      its taxonomy ("separate small local vision model" was jargon soup). */}
                  <p className="kc-wiz-model-desc">
                    KimCad’s local AI — runs on your CPU, no internet required. It’s the tested
                    default for designing parts. A second small download lets KimCad read photos and
                    sketches (<code className="kc-mono">{model?.vision_model ?? 'qwen2.5vl:3b'}</code>).
                  </p>
                  {/* UX-902 (stage-9 gate) + Slice 10.4: the SECOND model is checked too, and
                      "get the model" is now an in-app DOWNLOAD with progress — the server
                      decides what's missing (chat and/or vision); the button just says go.
                      Designing in words works without the vision model, so a vision-only gap
                      is an action line, never a blocker. */}
                  {/* UX-A-001 (stage-A gate): the action line + its button stay MOUNTED while a
                      re-check is in flight (last-known state drives visibility), so keyboard
                      focus never drops and the wizard's Tab trap can't be escaped mid-check. */}
                  {model?.backend === 'local' && !model.running && (
                    <p className="kc-wiz-model-action">
                      Start Ollama, then{' '}
                      <button
                        type="button"
                        className="kc-link-btn"
                        aria-disabled={modelState === 'checking' || undefined}
                        onClick={() => {
                          if (modelState !== 'checking') checkModel()
                        }}
                      >
                        {modelState === 'checking' ? 'checking…' : 'check again'}
                      </button>
                      . You can finish setup either way.
                    </p>
                  )}
                  {/* The live region stays MOUNTED (UX-A-001 pattern) and carries only the
                      coarse announcement — see pullAnnouncement above. */}
                  <p className="kc-sr-only" role="status">{pullAnnouncement}</p>
                  {model?.backend === 'local' && model.running &&
                    (!model.model_present || model.vision_present === false) && (
                    <div className="kc-wiz-pull">
                      {!pull && (
                        <p className="kc-wiz-model-action">
                          {!model.model_present
                            ? 'The design model isn’t downloaded yet.'
                            : 'Photos and sketches need one more download — designing in words works without it.'}{' '}
                          <button type="button" className="kc-btn kc-btn-accent kc-wiz-pull-btn" onClick={beginPull}>
                            {!model.model_present
                              ? `Download now (~${model.vision_present === false ? 13 : 10} GB)`
                              : 'Download now (~3 GB)'}
                          </button>
                        </p>
                      )}
                      {pull?.error && (
                        <p className="kc-wiz-model-action kc-wiz-model-warn">
                          {pull.error}{' '}
                          {!pullActive && (
                            <button type="button" className="kc-link-btn" onClick={beginPull}>try again</button>
                          )}
                        </p>
                      )}
                      {pull && !pull.error && (
                        <ul className="kc-wiz-pull-rows">
                          {Object.entries(pull.models ?? {}).map(([name, st]) => (
                            <li key={name} className="kc-wiz-pull-row">
                              <code className="kc-mono">{name}</code>{' '}
                              {st.status === 'queued' && <span>waiting…</span>}
                              {st.status === 'pulling' && (
                                <span>
                                  downloading…{' '}
                                  {st.total > 0 ? `${Math.min(100, Math.round((st.completed / st.total) * 100))}%` : ''}
                                </span>
                              )}
                              {st.status === 'done' && <span>✓ done</span>}
                              {st.status === 'error' && (
                                <span className="kc-wiz-model-warn">
                                  {st.error}{' '}
                                  {!pullActive && (
                                    <button type="button" className="kc-link-btn" onClick={beginPull}>try again</button>
                                  )}
                                </span>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                      {/* The honest intermediate state: the design model is usable while the
                          vision model is still coming down. */}
                      {pullActive &&
                        (model.model_present || pull?.models?.[model.model]?.status === 'done') &&
                        model.vision_present === false && (
                        <p className="kc-wiz-model-action">
                          Designing in words works now — the photo &amp; sketch reader is still downloading.
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <div className="kc-wiz-cloud">
                  <label className="kc-wiz-cloud-toggle">
                    <input
                      type="checkbox"
                      checked={cloudOn}
                      onChange={(e) => setCloudOn(e.target.checked)}
                    />
                    Add an OpenRouter key for optional cloud speed-ups{' '}
                    <span className="kc-opt">(optional · local always works)</span>
                  </label>
                  {cloudOn && (
                    <div className="kc-wiz-cloud-fields">
                      <input
                        className="kc-text-input kc-mono"
                        type="password"
                        placeholder="Paste your OpenRouter key (sk-or-…)"
                        aria-label="OpenRouter API key"
                        autoComplete="off"
                        spellCheck={false}
                        value={keyDraft}
                        onChange={(e) => setKeyDraft(e.target.value)}
                      />
                      <input
                        className="kc-text-input kc-mono"
                        placeholder="Model slug (optional) — e.g. from openrouter.ai/models"
                        aria-label="OpenRouter model"
                        value={cloudModelDraft}
                        onChange={(e) => setCloudModelDraft(e.target.value)}
                      />
                      <p className="kc-wiz-cloud-note">
                        Used only when you opt into a cloud model. Sends your prompt off your machine;
                        never required to run KimCad.{' '}
                        {settings?.key_storage === 'file'
                          ? 'The key is kept in a settings file on this computer (the secure ' +
                            'credential store isn’t available here) — anyone who can read your ' +
                            'files could read it.'
                          : 'The key is kept in this computer’s secure credential store.'}
                      </p>
                    </div>
                  )}
                </div>
              </>
            )}

            {step === 2 && (
              <>
                <h1 id={headingId} className="kc-wiz-h1">
                  Your printer
                </h1>
                <p className="kc-wiz-lede">
                  This sets the build volume and slicing profile so KimCad’s checks match your
                  hardware. You can change it any time in Settings.
                </p>
                {printers.length === 0 ? (
                  <p className="kc-muted-note">
                    {settingsError
                      ? 'Couldn’t load your printers — you can pick one later in Settings.'
                      : 'Loading printers…'}
                  </p>
                ) : (
                  <ul className="kc-wiz-printers">
                    {printers.map((p) => {
                      const on = (settings?.default_printer ?? printers[0]?.key) === p.key
                      return (
                        <li key={p.key}>
                          <button
                            type="button"
                            className={`kc-wiz-printer${on ? ' on' : ''}`}
                            onClick={() => pickPrinter(p.key)}
                            aria-pressed={on}
                          >
                            <span className="kc-wiz-printer-radio" aria-hidden="true" />
                            <span className="kc-wiz-printer-name">{p.name}</span>
                            {!p.sliceable && (
                              <span className="kc-wiz-printer-note">no slicer profile yet</span>
                            )}
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </>
            )}

            {step === 3 && (
              <>
                <h1 id={headingId} className="kc-wiz-h1">
                  Direct printing
                </h1>
                <p className="kc-wiz-lede">
                  Optional. KimCad always lets you download a print-ready file. You can also connect a
                  printer to send jobs straight from the app — KimCad never auto-starts a print.
                </p>
                <div className="kc-wiz-direct">
                  <button
                    type="button"
                    className={`kc-wiz-direct-opt${!directLater ? ' on' : ''}`}
                    onClick={() => setDirectLater(false)}
                    aria-pressed={!directLater}
                  >
                    <span className="kc-wiz-direct-t">Just download files</span>
                    <span className="kc-wiz-direct-d">
                      Export a 3MF / STL and print it however you like.
                    </span>
                  </button>
                  <button
                    type="button"
                    className={`kc-wiz-direct-opt${directLater ? ' on' : ''}`}
                    onClick={() => setDirectLater(true)}
                    aria-pressed={directLater}
                  >
                    <span className="kc-wiz-direct-t">I’ll connect a printer later</span>
                    {/* UX-1001 closed at Slice 11.2: the Settings venue exists now. */}
                    <span className="kc-wiz-direct-d">
                      Connect one any time in Settings → Printer connections.
                    </span>
                  </button>
                </div>
              </>
            )}

            {step === 4 && (
              <>
                {/* UX-002: the recap tells the truth about the model's CURRENT state. "You're
                    all set" with a dead model is exactly the trust-breaking first impression a
                    beta must avoid — so a not-ready model demotes the headline and the recap
                    row carries the fix + a re-check, while "Start designing" stays available. */}
                {modelOk ? (
                  <div className="kc-wiz-done-badge" aria-hidden="true">
                    ✓
                  </div>
                ) : null}
                <h1 id={headingId} className="kc-wiz-h1">
                  {modelOk ? 'You’re all set' : 'Almost ready'}
                </h1>
                <p className="kc-wiz-lede">
                  {modelOk
                    ? 'KimCad is ready to design. Here’s your setup — change any of it later from Settings.'
                    : 'One thing still needs attention before KimCad can design — everything else is saved. You can change any of this later from Settings.'}
                </p>
                {/* UX-1002 (stage-10 gate): a download the USER started must not vanish from
                    the recap — "all set" while the vision model is still coming down (or its
                    download was never finished) overstates what works today. */}
                {modelOk && pullActive && (
                  <p className="kc-wiz-lede kc-wiz-recap-pull">
                    The photo &amp; sketch reader is still downloading — it finishes in the
                    background; designing in words already works.
                  </p>
                )}
                {modelOk && !pullActive && model?.vision_present === false && (
                  <p className="kc-wiz-lede kc-wiz-recap-pull">
                    Photos and sketches still need their download — the model step has the
                    button. Designing in words already works.
                  </p>
                )}
                <dl className="kc-wiz-recap">
                  <div className="kc-wiz-recap-row">
                    <dt>Model</dt>
                    <dd className="kc-mono">
                      {model?.model ?? 'gemma4:e4b'}
                      {/* Only claim "+ OpenRouter" when it's actually usable — cloud routes only
                          with a key AND a model; a key alone is saved but stays inactive. */}
                      {cloudOn && keyDraft.trim() && cloudModelDraft.trim() ? ' + OpenRouter' : ''}
                      {/* UX-A-001/002: mounted through re-checks (no focus loss, reliable SR
                          announcement); the button no-ops while checking instead of unmounting. */}
                      {!modelOk && (
                        <span className="kc-wiz-model-warn kc-wiz-recap-warn" role="status">
                          {' '}
                          <span className="kc-statdot kc-statdot-warn" aria-hidden="true" />{' '}
                          {/* UX-001 (slice-10.4 audit): mid-download, the recap must not
                              tell the user to pull manually — that contradicts the
                              download THEY started on the model step. */}
                          {pullActive
                            ? 'downloading now — it continues in the background; when it finishes, '
                            : model && model.running && !model.model_present
                              ? `not downloaded yet — use Download on the model step (or run “ollama pull ${model.model}”), then `
                              : 'not reachable yet — start Ollama, then '}
                          <button
                            type="button"
                            className="kc-link-btn"
                            aria-disabled={modelState === 'checking' || undefined}
                            onClick={() => {
                              if (modelState !== 'checking') checkModel()
                            }}
                          >
                            {modelState === 'checking' ? 'checking…' : 'check again'}
                          </button>
                        </span>
                      )}
                    </dd>
                  </div>
                  <div className="kc-wiz-recap-row">
                    <dt>Printer</dt>
                    <dd>{chosenPrinter?.name ?? '—'}</dd>
                  </div>
                  <div className="kc-wiz-recap-row">
                    <dt>Direct printing</dt>
                    <dd>{directLater ? 'Set up later in Settings' : 'File download'}</dd>
                  </div>
                </dl>
              </>
            )}
          </div>

          <div className="kc-wiz-foot">
            <button
              type="button"
              className="kc-btn kc-wiz-back"
              onClick={back}
              disabled={step === 0}
              style={{ visibility: step === 0 ? 'hidden' : 'visible' }}
            >
              Back
            </button>
            <div className="kc-wiz-dots" aria-hidden="true">
              {STEPS.map((s, i) => (
                <span key={s} className={`kc-wiz-dot${i === step ? ' on' : ''}`} />
              ))}
            </div>
            {step < STEPS.length - 1 ? (
              <button type="button" className="kc-btn kc-btn-accent" onClick={next}>
                Continue
              </button>
            ) : (
              <button type="button" className="kc-btn kc-btn-accent" onClick={finish}>
                Start designing
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
