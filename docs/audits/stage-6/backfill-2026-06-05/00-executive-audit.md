# Stage 6 (model layer: hardware advisor + tiered fallback + bake-off) — backfill audit, exec summary
**Date:** 2026-06-05 · **Scope:** the CURRENT `main` code of the model layer — `model_advisor.py`
(hardware probe, `recommend`, the catalog, the gemma4-top/Qwen-deprioritized ranking), `bakeoff.py`,
the tiered `FallbackProvider` + model-down handling (`llm_provider.py`, `pipeline.py`), and the
Settings model/cloud surface (`/api/model-status`, `/api/settings`, `SettingsPanel.tsx`). Audited
live + statically.
**Standing constraint honored:** `gemma4:e4b` is THE model — the advisor's gemma4-top/Qwen-deprioritized
design and the one-model (no-picker) Settings UI are correct by design; agents were instructed not to
flag them, and none did.

## Method (real skills, independent agents)
Round 1 — six independent agents (`wiring-audit` on the Settings model surface + five `audit-team`
deep-dives). Round 2 — an independent re-audit agent (live UI + backend + docs), confirming the
fixes both ways on the running app.

## Round-1 severity rollup (deduped)
Blocker 0 · **Critical 1** · **Major 2** · Minor 6 · Nit 3. The engineering deep-dive on the advisor
logic itself was 0/0/0/0/0 — the decision is genuinely pure, the probes tolerate a down/garbage
Ollama, model-down degrades to a typed status (never a 500), and the cloud key is never logged.

## The real bugs (found → fixed → verified)
- **UX-001 / wiring H-1 (Critical):** the Settings AI-model card hard-coded "KimCad's local AI…
  nothing leaves your computer" **even when the cloud backend was active** — a flat contradiction of
  the product's core privacy promise (cloud DOES send off-machine). Fixed by branching the
  description on the live `model.backend`: cloud now reads "runs on OpenRouter's servers… your
  prompt is sent to the cloud," local keeps the on-device copy. Verified live both ways.
- **DOC-001 (Major):** the README prose named only "DeepSeek / any OpenAI-compatible endpoint" and
  omitted **OpenRouter** — the blessed in-app cloud path the Settings UI is built around. Fixed
  (README now names the in-app OpenRouter opt-in + a "verify the cloud model_name" caveat for the
  example tags).
- **TEST-101 (Major):** the model layer is the secret-holding path, but unlike the connectors it had
  no test pinning the cloud API key out of the fallback's stderr log. The key was already safe (the
  switch log prints the backend's config name, not the key); added a regression test that fails if a
  key value ever reaches stderr.

## Other fixes (every finding, Blocker→Nit)
- **QA-001 (Minor):** `_mask_key` revealed the last-5 for keys >8 chars — for a 9-12 char value that's
  up to half the key. Raised the threshold to ≥16 so short keys reveal nothing. **QA-002 (Minor):** a
  POST to a GET-only resource (`/api/model-status`, `/api/options`, `/api/health`, …) now returns
  405 + an `Allow` header instead of a misleading 404.
- **DOC-003 (Minor):** the Qwen 3B/7B catalog notes said "REJECTED" though only the 1.5B was
  bench-tested — softened to "deprioritized (not bench-tested)"; the 1.5B keeps its measured-rejected
  note. **DOC-004** confirmed already-accurate (the bake-off doc states "~10 min/prompt" plainly,
  matching the recorded 595.7 s — no "fast" overclaim).
- **UX-003/004/005:** mobile cloud key/model fields now align (the Save/Replace button drops to its
  own full-width row); a disabled button no longer captures pointer events; the "Experimental ·
  Untrusted" badge text darkened above the AA floor.
- **TEST-103 (Minor):** a regression test that a zero-completion bake-off renders "n/a" + an explicit
  note, never a "0/0" that scans as a real score — the exact anti-pattern that once masked a dead
  LLM. Plus the UX-001 copy test (cloud vs local).
- **M-1** (demo still probes real Ollama for model-status) confirmed acceptable-by-design — it's a
  machine-readiness readout, not a claim the demo uses the model. **ENG-503** (single render lock),
  **TEST-102/104, QA-003** noted as documented/accepted minors (defensive branches / lenient bool
  coercion); none affect correctness or the zero-findings bar.

## Round-2 re-audit
CLEAN — all 8 actioned findings verified resolved on the running app; the Critical confirmed both
ways (cloud copy honest, local copy on-device); false-green check passes (TEST-101 + TEST-103 fail if
reverted). The advisor-logic engineering pass remained 0 findings.

## Final verdict
**STAGE 6 BACKFILL: CLEAN — 0/0/0/0/0 across all five lanes + wiring-audit PASS.**
Gate green: ruff, geometry backends, 773 pytest (not-live), 278 vitest, SPA build reproducible.
