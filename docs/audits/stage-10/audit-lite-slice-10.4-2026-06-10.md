# Audit Lite — Stage 10 Slice 10.4 (wizard model pulls + Settings vision row)
**Date:** 2026-06-10
**Scope:** Uncommitted working tree on top of 75690ab — `src/kimcad/model_pull.py` + `tests/test_model_pull.py` (new), `webapp.py` routes, `frontend/src/api.ts`, `FirstRunWizard.tsx` (+tests), `SettingsPanel.tsx`, `styles.css`, troubleshooting/ARCHITECTURE rows. Built assets excluded.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship with caveats. The hard parts are right: the lock discipline is correct (the `_snapshot_locked` fix holds — every path under `start()`'s lock uses it), the 300 s timeout is **per-read**, not total (verified empirically with a 2.4 s stream surviving `timeout=1`), the pull list is genuinely fixed server-side, the loopback gate works, `not_local`'s 400 JSON body does reach the typed branch in `startModelPull`, and the size claims (~13/10/3 GB) are honest against the real 9.6 + 3.2 GB. One Major: the whole progress block is a `role="status"` live region updated at 1 Hz — for a screen-reader user a 30–60 minute download means the entire block re-announced every second. The rest is small: a recap-step copy contradiction mid-pull, an interval leak on one unmount race, stale per-model residue on the disk-precheck path (reproduced), and a few test/doc gaps.

## Verification run (this audit, not the dev's claims)
- `.venv\Scripts\python.exe -m pytest tests/test_model_pull.py -q` → **10 passed** (2.2 s)
- Full suite `.venv\Scripts\python.exe -m pytest -q` → **966 passed** (257 s)
- `.venv\Scripts\python.exe -m ruff check src tests` → **All checks passed**
- `vitest run src/components/FirstRunWizard.test.tsx` (node22) → **14 passed**
- Full `vitest run` → **328 passed** (26 files)
- Timeout semantics check: a streamed `urlopen(req, timeout=1)` survived a 2.4 s six-line drip-fed response → urllib's timeout is the **socket (per-read) timeout**; a >5-minute single-blob pull won't die spuriously while bytes flow. The doc claim "Ollama resumes a partial download" matches Ollama's documented blob-level resume behavior.
- Stale-residue repro: run 1 pulls `chat-model` to `done`; run 2 (vision only) hits the disk pre-check → snapshot still contains `chat-model: done` from the OLD run (see ENG-002).
- Monkeypatch binding check: `_handle_model_pull` imports `probe_ollama` at call time from `kimcad.model_advisor`, so the route tests' `monkeypatch.setattr(ma, "probe_ollama", …)` genuinely intercepts (and the tests prove it).

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 1
- Minor: 6
- Nit: 4

## Findings

### A11Y-001 Major: The 1 Hz progress block is a `role="status"` live region — screen readers re-announce it every second for the whole download
**Dimension:** Accessibility
**Evidence:** `frontend/src/components/FirstRunWizard.tsx:323` — the entire `.kc-wiz-pull` container carries `role="status"` (implicit `aria-live="polite"` **and `aria-atomic="true"`**). The poll updates the percent text every 1000 ms, so for the duration of a ~10 GB pull (tens of minutes) an SR user gets the whole block — model names, percents, the works-in-words line — queued for re-announcement every second. This is the opposite of the project's own a11y record (UX-A-001/002 were specifically about *reliable, non-spammy* SR announcements in this wizard).
**Why it matters:** The flagship UX of this slice is effectively unusable with a screen reader while it's doing its job.
**Fix path:** Move the live region to the *state transitions* only: a visually-hidden `role="status"` node announcing "Download started", per-model "done"/"error", and "All downloads finished" (or throttled \~every 10%), with the percent rows plain non-live content (`aria-live` off). Small, local change; the existing vitest cases don't assert the role so they keep passing.

### UX-001 Minor: The recap step contradicts an in-flight download — "run `ollama pull …`" while the in-app pull is running
**Dimension:** UX honesty
**Evidence:** `FirstRunWizard.tsx:537` — step 4's not-ready row says `not pulled yet — run "ollama pull <model>", then check again`. The pull state (`pull`, `pullActive`) lives at component level and the user can hit Continue → recap mid-download (likely: they just pressed Download and click through). The recap re-probe (UX-002) still sees `model_present: false`, so the wizard simultaneously downloads the model and tells the user to go pull it manually in a terminal.
**Why it matters:** Exactly the trust-breaking mixed message the recap step's own comment promises to avoid; a user may start a second, competing `ollama pull`.
**Fix path:** When `pullActive` (or `pull?.models?.[model.model]` is `queued|pulling`), the recap row should say "downloading now — N%" (or just "downloading in the background") instead of the manual instruction.

### ENG-001 Minor: Unmount between Download click and `startModelPull` resolving leaks the 1 s poll forever
**Dimension:** Correctness / lifecycle
**Evidence:** `FirstRunWizard.tsx:91-110` — `beginPull` creates the interval inside `startModelPull().then(...)`. If the wizard unmounts (Escape / Start designing) after the click but before the POST resolves, the unmount cleanup (`useEffect(() => stopPolling, …)`) runs first, then the `.then` installs a fresh interval into a ref nobody will ever clear — `getModelPullProgress` fires every second for the rest of the page session (and `checkModel`/`setPull` land on a dead component). The comment "The poll dies with the wizard" is not true on this path. The other matrix cells are clean: plain unmount mid-poll is cleared by the effect cleanup; double-`beginPull` can't happen (the button unmounts once `pull` is set, retry buttons render only when `!pullActive`); step navigation keeps the component mounted so polling correctly continues.
**Why it matters:** Harmless-looking but permanent background network chatter, and it masks the job's end (no re-probe ever runs for whoever reopens the wizard — though reopening re-probes on mount anyway).
**Fix path:** A `disposed` ref set in an unmount effect; `beginPull`'s `.then` checks it before installing the interval (and `stopPolling` style cleanup stays as is).

### ENG-002 Minor: Per-model states from a PREVIOUS run leak into the current snapshot on two paths
**Dimension:** Correctness
**Evidence:** `src/kimcad/model_pull.py:109-117` — the disk-precheck failure path assigns `self._models[name] = …` per missing name **without replacing the dict**, so entries from an earlier finished run survive (reproduced: run 1's `chat-model: done` appears in run 2's vision-only precheck-failure snapshot). Similarly `start()` with `missing == []` (line 101-102) returns the old run's full state as the "current" answer. The happy path is fine — line 117 replaces the dict wholesale. Client-side the poll merge is safe (`setPull((prev) => ({...prev, ...p}))` replaces `models` as a whole key, no cross-run row mixing).
**Why it matters:** Today the leak is mostly benign (a stale `done` row, or stale `error` rows shown when the server finds nothing missing — reachable only through a probe race), but it's the kind of latent state bug that bites when a later slice reads the snapshot for something load-bearing.
**Fix path:** In the precheck branch build a fresh dict exactly like line 117 does; optionally clear `_models` when `missing` is empty and the thread is dead.

### ENG-003 Minor: Disk pre-check measures the home drive, but `OLLAMA_MODELS` can put blobs elsewhere
**Dimension:** Correctness
**Evidence:** `model_pull.py:107` — `shutil.disk_usage(probe_dir or Path.home())`. Ollama honors `OLLAMA_MODELS` (and Windows service installs sometimes relocate it); a user with a full C: but models on a roomy D: gets a false "Not enough disk space" refusal, and the inverse gets a late mid-stream disk-full (which the friendly mapping does catch — so this degrades, not breaks).
**Fix path:** `Path(os.environ.get("OLLAMA_MODELS") or Path.home())` (existence-guarded) as the probe dir.

### ENG-004 Minor: Demo mode leaves `POST /api/model-pull` fully live — a demo walkthrough click can start a real ~13 GB download
**Dimension:** Correctness / blast radius
**Evidence:** `webapp.py:1132` — `_handle_model_pull` reads the real `get_config()` regardless of the `demo` flag (`build_web_pipeline` swaps only the provider). With the default local config the loopback + probe gates pass on any dev box running Ollama, so the demo wizard's Download button triggers genuine multi-gigabyte pulls. Consistent with `/api/model-status` already probing the real Ollama in demo mode — but a probe is cheap and a pull is not, and the demo's stated contract is "a UI check never pollutes the user's …" state.
**Fix path:** Either accept it explicitly (a comment — the download is real on purpose, demo is local-dev-only) or have the demo handler return a canned `{status: "ok", running: true, …}` progression like the canned vision seed does.

### TEST-001 Minor: Two untested seams — `startModelPull`'s `not_local` pass-through and the Settings vision row
**Dimension:** Tests
**Evidence:** `frontend/src/api.test.ts` has no case for `startModelPull` — it is the only fetch wrapper in `api.ts` with a non-throwing 400 path (`api.ts:362-364`), exactly the kind of special case a refactor of `readJson`/`throwIfNotOk` would silently break (I traced it by hand: `readJson` parses the 400 body, the status guard skips `throwIfNotOk` — correct today). `frontend/src/components/SettingsPanel.test.tsx` has zero coverage of the new vision row (present / not-present / absent-fields-say-nothing). The pytest side is solid (10 targeted tests incl. all four route behaviors); a snapshot-after-finished-run staleness test is worth adding alongside the ENG-002 fix but isn't a gap that hides a regression today.
**Fix path:** One api.test.ts case (mock 400 + `{status:"not_local"}` → resolves, not rejects), two or three SettingsPanel cases.

### UX-002 Nit: Progress percent is per-blob, so it can jump backward between layers
`model_pull.py:163-165` — `total`/`completed` come from each stream line, and Ollama reports them per digest/layer; when the pull moves from the main blob to the next layer the percent restarts. For these models one blob dominates so it reads fine in practice; cosmetic.

### ENG-005 Nit: `is_loopback_url` prefix-matches hostnames against `"127."`
`model_pull.py:48-49` — `host.startswith("127.")` accepts a DNS name like `127.evil.example`, and `"::1"` misses the long-form IPv6 loopback. The base_url comes from the user's own local config (trusted), so impact is ~zero; an `ipaddress.ip_address(...).is_loopback` attempt with a string fallback would be exact.

### DOC-001 Nit: Markdown seam + one stale guide paragraph
`docs/troubleshooting.md:81-82` — the new Bambu section runs straight into the `## "OpenSCAD isn't installed…"` heading with no blank line (renders under CommonMark, but breaks the file's own convention and stricter renderers). `docs/guide-settings-and-cloud.md:14-22` still presents `ollama pull qwen2.5vl:3b` as the only fix and says Settings shows "whether … the design model is pulled" — not contradicted, but it predates both the new Settings vision row and the wizard's in-app download; one sentence brings it current. The "Ollama resumes a partial download" claim checks out (blob-level resume is Ollama's documented behavior). README's manual `ollama pull` lines remain a valid alternate path — no contradiction there.

### UX-003 Nit: Settings vision row — duplicate refresh affordances and an unstyled hook class
`SettingsPanel.tsx:269-281` — the row's "check again" link sits a few lines above the card's existing **Refresh** button (`:299-300`), both calling `checkModel`; the new link also skips the `aria-disabled`-while-checking pattern the wizard's equivalent buttons use. `kc-set-vision-row` has no rule in `styles.css` (hook-only class — fine if intentional, noise if not). Copy is consistent with the wizard ("photos and sketches", "check again") — good.

## Cleared (checked, no finding)
- **Lock discipline:** every path inside `start()`'s `with self.lock:` uses `_snapshot_locked`; the worker takes the lock for every mutation; the lock is never held across I/O. No remaining reentrancy or race found (the alive-check/start sequence is fully under one lock acquisition).
- **Shallow copy depth:** per-model state dicts hold only scalars, so `dict(s)` per model is a complete defensive copy.
- **JOB global:** unit tests construct their own `ModelPullJob`s; the route tests either read the untouched global or patch `ModelPullJob.start` — no cross-test pollution; a server restart is a process restart.
- **`not_local` wire format:** 400 + JSON body parses through `readJson` and skips `throwIfNotOk` — the wizard receives the typed status (traced; untested in JS, see TEST-001).
- **Size honesty:** ~13 / ~10 / ~3 GB vs real 9.6 + 3.2 GB — rounded up, honest.
- **Fixed server-side list:** the POST reads no request body; names come from config with the same defaults and the same `tag`/`tag-variant` matching as `/api/model-status`.
- **Cloud-enabled users:** `model-pull` ignores the cloud override and pulls the local models — correct, since the vision read is always local.

## Escalation verdict
**No escalation to audit-team.** Zero Blocker/Critical; the single Major is a contained accessibility fix in one component, and every Minor has a small, local fix path. Recommend fixing A11Y-001, UX-001, ENG-001, ENG-002 before the slice commit; the rest fold into the same pass per the zero-at-all-levels standard.
