import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { isAbortError, uploadPhoto, uploadSketch } from '../api'

// Stage 8.5 Slice 7 (Surface D) — the "describe with a photo" on-ramp.
// A secondary affordance beside the text box: pick (or drop) a photo, KimCad's LOCAL vision reads
// it into a ROUGH, editable text seed, and "Use this as a starting point" feeds the normal
// text->DesignPlan flow. Honest framing throughout — a photo carries no scale, so sizes are
// estimates; the photo is read locally and never auto-sends off the machine; the delivered geometry
// is always KimCad's own deterministic output, never the raw image.

type Phase = 'idle' | 'reading' | 'confirm' | 'error'

function CameraGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 8.5A1.5 1.5 0 0 1 4.5 7h2L8 5h8l1.5 2h2A1.5 1.5 0 0 1 21 8.5v9A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5Z" />
      <circle cx="12" cy="13" r="3.2" />
    </svg>
  )
}

function PencilGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17 3.5 20.5 7 8.5 19l-4.5 1 1-4.5Z" />
      <path d="m14.5 6 3.5 3.5" />
    </svg>
  )
}

// Stage 9: the same on-ramp flow serves photos AND dimensioned sketches — only the endpoint,
// the wording, and the scale note differ (a sketch CARRIES its dimensions; a photo estimates).
const KIND_COPY = {
  photo: {
    affordance: 'Describe with a photo',
    noun: 'photo',
    reading: 'Reading your photo…',
    scaleNote: 'A photo can’t tell us scale, so any sizes are estimates. Adjust anything, then continue.',
    cantRead: 'Couldn’t read that photo — try a clearer shot, or cancel and describe the part in words.',
    upload: uploadPhoto,
  },
  sketch: {
    affordance: 'Start from a sketch',
    noun: 'sketch',
    reading: 'Reading your sketch…',
    scaleNote: 'Labeled dimensions are read as written — check they came through, then continue.',
    cantRead: 'Couldn’t read that sketch — try a clearer image with written dimensions, or cancel and describe the part in words.',
    upload: uploadSketch,
  },
} as const

export default function PhotoOnramp({
  onSeed,
  disabled = false,
  variant = 'landing',
  kind = 'photo',
}: {
  onSeed: (seed: string) => void
  disabled?: boolean
  variant?: 'landing' | 'workspace'
  kind?: 'photo' | 'sketch'
}) {
  const copy = KIND_COPY[kind]
  const [phase, setPhase] = useState<Phase>('idle')
  const [seed, setSeed] = useState('')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const seedRef = useRef<HTMLTextAreaElement>(null)
  const errorRef = useRef<HTMLParagraphElement>(null)
  // Lets the user cancel a slow local-vision read (the photo never auto-sends, but the read can take
  // ~15-20s on CPU — they must be able to back out).
  const readAbortRef = useRef<AbortController | null>(null)

  // MS2-001: revoke the preview blob URL on change/unmount so a photo read that's abandoned
  // mid-flow (navigate away from the confirm/error card) doesn't leak the object URL.
  useEffect(() => {
    if (!previewUrl) return
    return () => URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  // MS2-002: when the rough seed lands, move focus to the editable field — this announces it to
  // assistive tech (the reading aria-live region is gone) and lets a sighted user edit immediately.
  useEffect(() => {
    if (phase === 'confirm') seedRef.current?.focus()
  }, [phase])

  // UX-906 (stage-9 gate): a failed read moves focus to the message itself — the seed
  // field the user was headed for never appeared, and without a focus move a keyboard or
  // screen-reader user is left where the spinner used to be with no announcement.
  useEffect(() => {
    if (phase === 'error') errorRef.current?.focus()
  }, [phase])

  function clearPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null)
  }

  function reset() {
    clearPreview()
    setSeed('')
    setErrorMsg('')
    setPhase('idle')
  }

  // Cancel an in-flight vision read and return to the affordance (the abort throws in handleFile,
  // whose catch resets to idle). Abort any in-flight read on unmount too, so navigating away doesn't
  // leave it running.
  function cancelRead() {
    readAbortRef.current?.abort()
  }
  useEffect(() => () => readAbortRef.current?.abort(), [])

  async function handleFile(file: File | undefined | null) {
    if (!file || disabled) return
    readAbortRef.current?.abort() // supersede any prior read
    const controller = new AbortController()
    readAbortRef.current = controller
    // Show a local preview thumbnail immediately ("I saw your photo") — created from the in-memory
    // file, nothing uploaded for the preview. Revoke the previous object URL so we don't leak it.
    clearPreview()
    setPreviewUrl(URL.createObjectURL(file))
    setErrorMsg('')
    setPhase('reading')
    try {
      const res = await copy.upload(file, controller.signal)
      const text = (res.seed ?? '').trim()
      if (!text) {
        setErrorMsg(copy.cantRead)
        setPhase('error')
        return
      }
      setSeed(text)
      setPhase('confirm')
    } catch (err) {
      if (isAbortError(err)) {
        reset() // the user cancelled — back to the affordance, quietly (no error)
        return
      }
      setErrorMsg(err instanceof Error ? err.message : copy.cantRead)
      setPhase('error')
    } finally {
      if (readAbortRef.current === controller) readAbortRef.current = null
    }
  }

  function onInputChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = '' // let the user re-pick the SAME file (otherwise onChange won't fire again)
    void handleFile(file)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    if (disabled) return
    void handleFile(e.dataTransfer.files?.[0])
  }

  function openPicker() {
    if (!disabled) inputRef.current?.click()
  }

  function useSeed() {
    const text = seed.trim()
    if (!text || disabled) return
    reset()
    onSeed(text)
  }

  return (
    <div className={`kc-photo-onramp kc-photo-${variant} kc-onramp-${kind}`}>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="kc-photo-file"
        onChange={onInputChange}
        hidden
      />

      {phase === 'idle' && (
        <button
          type="button"
          className="kc-photo-affordance"
          onClick={openPicker}
          disabled={disabled}
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
        >
          {kind === 'sketch' ? <PencilGlyph /> : <CameraGlyph />}
          {copy.affordance}
          {/* UX-910 (stage-9 gate): the buttons accept drag-and-drop but nothing said so. */}
          <span className="kc-photo-drophint">— or drop an image here</span>
        </button>
      )}

      {phase !== 'idle' && (
        <div
          className={`kc-photo-card${phase === 'error' ? ' kc-photo-card-error' : ''}`}
          role="group"
          aria-label={
            phase === 'error'
              ? // UX-909 (stage-9 gate): neutral — the failure may be a missing model or a
                // busy server, not the image; "couldn't be read" wrongly blames the picture.
                `Something went wrong reading your ${copy.noun}`
              : phase === 'reading'
                ? `Reading your ${copy.noun}`
                : `A rough starting point from your ${copy.noun}`
          }
        >
          {phase === 'reading' && (
            <>
              <div className="kc-photo-row" aria-live="polite">
                {previewUrl && <img className="kc-photo-thumb" src={previewUrl} alt="" />}
                <div className="kc-photo-body">
                  <span className="kc-photo-title">
                    <span className="kc-spin" aria-hidden="true" /> {copy.reading}
                  </span>
                  <p className="kc-photo-privacy">
                    Your {copy.noun} stays on your computer — KimCad’s local vision reads it into a
                    rough starting point. It never leaves your machine. This can take a moment on
                    your computer’s AI.
                  </p>
                </div>
              </div>
              <div className="kc-photo-actions">
                <button type="button" className="kc-btn kc-btn-ghost" onClick={cancelRead}>
                  Cancel
                </button>
              </div>
            </>
          )}

          {phase === 'confirm' && (
            <>
              <div className="kc-photo-row">
                {previewUrl && <img className="kc-photo-thumb" src={previewUrl} alt="" />}
                <div className="kc-photo-body">
                  {/* UX-903 (stage-9 gate): the visible title names the source too — with two
                      on-ramps side by side, sighted users need the same disambiguation the
                      group label already gives assistive tech. */}
                  <span className="kc-photo-title">
                    A rough starting point — from your {copy.noun}
                  </span>
                  {/* UX-102 (stage-BCD gate): ONE privacy line covering both halves of the
                      promise (read locally + not saved) — was two near-duplicate notes. */}
                  <p className="kc-photo-privacy">
                    Read locally — your {copy.noun} never left your machine and isn’t saved; only
                    this description continues.
                  </p>
                </div>
              </div>
              <textarea
                ref={seedRef}
                className="kc-photo-seed"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                aria-label={`Edit the description read from your ${copy.noun}`}
                rows={3}
                disabled={disabled}
              />
              <p className="kc-photo-note">{copy.scaleNote}</p>
              {variant === 'workspace' && (
                <p className="kc-photo-note">
                  This starts a new part from the {copy.noun} — your current part is saved in My Designs.
                </p>
              )}
              <div className="kc-photo-actions">
                <button
                  type="button"
                  className="kc-btn kc-btn-accent"
                  onClick={useSeed}
                  disabled={disabled || seed.trim() === ''}
                >
                  Use this as a starting point
                </button>
                <button type="button" className="kc-btn kc-btn-ghost" onClick={openPicker} disabled={disabled}>
                  Use a different {copy.noun}
                </button>
                <button type="button" className="kc-photo-cancel" onClick={reset}>
                  Cancel
                </button>
              </div>
            </>
          )}

          {phase === 'error' && (
            <>
              <p className="kc-photo-error-msg" aria-live="polite" tabIndex={-1} ref={errorRef}>
                {errorMsg}
              </p>
              <div className="kc-photo-actions">
                <button type="button" className="kc-btn kc-btn-accent" onClick={openPicker} disabled={disabled}>
                  Use a different {copy.noun}
                </button>
                <button type="button" className="kc-photo-cancel" onClick={reset}>
                  Cancel
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
