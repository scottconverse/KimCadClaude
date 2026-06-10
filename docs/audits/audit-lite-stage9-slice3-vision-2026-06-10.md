# Audit Lite — Stage 9 Slice 3: the vision-model fix + on-target measurements + photo-3D verdict
**Date:** 2026-06-10
**Scope:** The dedicated local vision model (`vision_model: qwen2.5vl:3b` on the backend config; `_describe_image` targets it; the obsolete `think:false` dance removed), typed `VisionModelMissing` (Ollama 404 → "ollama pull qwen2.5vl:3b" on both image endpoints), `kimcad models` reports the vision model's state, docs corrected everywhere the old single-model vision claim lived (README setup + claims, getting-started Step 2, troubleshooting ×2, guide-photo-onramp, the wizard model card), and `docs/benchmarks/stage-9-vision-onramps.md` (all measurements + the photo→3D descope verdict).
**Reviewer:** Claude (audit-lite) — adversarial self-review.

## TL;DR
Ship. This slice **found and fixed a Critical latent product defect**: gemma4:e4b's vision is broken on this stack — the model itself reports "no visible image was provided," and with `think:false` it deterministically hallucinates the *same* description for any image. That means the shipped Stage 8.5 photo on-ramp never worked against the real pinned model; every live impression was demo mode, and the one test pinning the transport pinned the broken wiring (`think:false`) rather than an outcome. The fix is measured, not assumed: qwen2.5vl:3b reads the L-bracket sketch **5/5 end-to-end through KimCad's own endpoint in 27.7 s** on the target box. The photo→3D reconstruction experiment is descoped with evidence, per the ROADMAP's own exit criteria.

## Severity rollup (this slice's own work)
Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 0 — **0/0/0/0/0**
(The Critical it FIXED is recorded as a finding against the inherited Stage 8.5/9.1 work in the benchmark doc and will appear in the stage gate's record.)

## Adversarial checks performed
- **Was the defect real, not my harness?** Isolation matrix: 2 grossly different images × {think:false, think:true, no-think, /api/generate, JPEG} — all failed, including the model's own "no image provided" admission. Split test: moondream through the *identical* request shape read the image — Ollama's plumbing exonerated, the model build convicted.
- **Is the fix the right size?** moondream (1.7 GB) measured first and rejected on evidence (empty on instruction prompts). qwen2.5vl:3b measured at 3/3 dims + thickness + shape, then **re-proven through KimCad's real endpoint** (5/5, 27.7 s). The diagnostic moondream pull was removed.
- **Failure modes:** missing vision model → typed pull-command response on BOTH endpoints (tested); down server → existing typed mapping unchanged (covered by prior tests); empty read → the 422 guidance with the stderr hint updated to the new model.
- **Test honesty:** the old `think:false` pin was *updated to pin the outcome* (vision model targeted, image attached) — the new provider test additionally asserts the chat model is NOT used for vision.
- **Trust boundary:** unchanged and re-asserted — same local Ollama host, transport-level test still pins localhost + `/api/chat`; all doc copy updated says "local vision model," never weakening the never-leaves-the-machine promise.
- **Setup-surface completeness:** the second pull appears in README Setup, getting-started Step 2, troubleshooting, `kimcad models` output, and the wizard's model description — grep confirms no surviving "handles everything, including reading a photo" claim.

## Tests
4 new/updated (provider vision-target + 404-typed; webapp both-endpoints typed mapping; the legacy transport pin rewritten). Full suite **918 passed** · vitest 308 · ruff clean · typecheck · byte-exact build.

## Escalation recommendation
No escalation — but the stage gate's record must carry the inherited-defect finding (it will).
