# Audit Lite — Stage 9 Slice 1: SKETCH on-ramp backend
**Date:** 2026-06-06
**Scope:** The sketch on-ramp backend — a dimensioned sketch → local vision → editable text seed → existing text→DesignPlan path. Reviewed `src/kimcad/prompts/system_sketch_seed.md` (new), the `_describe_image`/`describe_photo`/`describe_sketch` refactor in `src/kimcad/llm_provider.py`, the `POST /api/sketch-seed` route + `_handle_sketch_seed` and the `DemoProvider`/`_SettingsAwareProvider` `describe_sketch` additions in `src/kimcad/webapp.py`, and the four touched test files.
**Reviewer:** Claude (audit-lite)
**Branch / tree state:** `stage-9-image-onramp`, uncommitted working tree (5 modified + 1 untracked). Audit-only — no repo files changed except this report.

## TL;DR
Ship-with-caveats. The refactor is clean and the photo path's behavior is preserved byte-for-byte; the sketch on-ramp correctly mirrors the photo on-ramp's trust boundary, robustness, and contract surface. ruff clean; the 12 targeted non-live tests (sketch + contract + photo) pass. The one real gap is **test coverage parity**: the load-bearing trust-rule test (sketch never routes to cloud) and the oversize/empty HTTP-guard tests exist for the photo path but were NOT mirrored for the sketch path. The sketch trust rule is correct in code today, but it is the highest-stakes invariant in this slice and it ships with no test pinning it — that is a Major test gap, not a correctness defect.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 1
- Minor: 2
- Nit: 1

## Findings

### FINDING-001 Major: The load-bearing "sketch never routes to cloud" trust rule has no test
**Dimension:** Tests
**Evidence:** The photo path pins this exact invariant with `test_photo_never_routes_to_cloud_even_when_cloud_enabled` (`tests/test_webapp.py:2741`), which enables cloud TEXT fully (key + model saved) and asserts `_SettingsAwareProvider.describe_photo` builds the LOCAL backend and never consults `_active()` (the cloud-capable router). The sketch equivalent — `_SettingsAwareProvider.describe_sketch` at `src/kimcad/webapp.py:464-470` — has the same load-bearing behavior but **no corresponding test**. The new sketch tests (`tests/test_webapp.py:2671-2702`) cover returns-seed-with-dims, unreadable-422, and empty-422 only. Similarly, the photo path pins the native-chat wiring with `test_llm_describe_photo_uses_native_chat_with_think_false` (`tests/test_webapp.py:2705`); there is no sketch-named twin (though see "What's working" — the shared helper means the photo test still exercises the sketch path's plumbing indirectly).
**Why it matters:** Per the project's own load-bearing trust boundary, an untrusted image must never auto-send off the machine even when cloud text is enabled. Today's code is correct, but with no test, a future refactor of `_SettingsAwareProvider` (e.g. routing `describe_sketch` through `_active()` to "simplify") would silently break the privacy guarantee and the suite would stay green. The photo path treats this as worth a dedicated, comment-flagged "LOAD-BEARING" test; the sketch path carries the identical risk and deserves the identical guard.
**Fix path:** Add `test_sketch_never_routes_to_cloud_even_when_cloud_enabled` mirroring the photo test at `tests/test_webapp.py:2741` (swap `describe_photo`→`describe_sketch` on the spy + the `_no_active` guard; assert `built == [cfg.llm_backend("local").key]` and `"custom_openrouter" not in built`). Optionally also add a sketch-named native-chat test, or parametrize the existing photo native-chat test over both wrappers, so the sketch wrapper's `prompt_name`/`user_msg` are pinned directly.
**Blast radius:**
- Adjacent code: `_SettingsAwareProvider.describe_photo` (the twin) is already pinned; this is purely additive test work.
- Tests to update: none existing — add one (ideally two) new tests in the Stage 9 block of `tests/test_webapp.py`.
- User-facing change: none (no production change).
- Migration concern: none.

### FINDING-002 Minor: Oversize (413) and empty-upload (400) HTTP guards are tested for photo but not sketch
**Dimension:** Tests
**Evidence:** The photo path has `test_photo_seed_oversized_is_413` (`tests/test_webapp.py:2603`) and `test_photo_seed_empty_upload_is_400` (`tests/test_webapp.py:2613`). `_handle_sketch_seed` (`src/kimcad/webapp.py:1405`) uses the SAME `_read_raw_body(MAX_PHOTO_BYTES)` helper (`src/kimcad/webapp.py:1761`) that returns the 413/400 responses, so the behavior is shared and the photo tests exercise that helper. But there is no sketch-route assertion that the route is wired to the guard (e.g. a regression that forgot to pass `MAX_PHOTO_BYTES`, or read the body before the guard, would not be caught on the sketch endpoint specifically).
**Why it matters:** Lower stakes than FINDING-001 because the guard logic is shared and already tested via the photo route. The risk is endpoint-specific wiring drift, which is real but narrow.
**Fix path:** Add `test_sketch_seed_oversized_is_413` and `test_sketch_seed_empty_upload_is_400` mirroring the photo versions via the existing `_post_sketch` helper (`tests/test_webapp.py:2653`) with `content_length=MAX_PHOTO_BYTES + 1` and `content_length=0`.

### FINDING-003 Minor: Sketch upload reuses `MAX_PHOTO_BYTES` and the 413 message says "File too large" with no sketch context
**Dimension:** Correctness / UX
**Evidence:** `_handle_sketch_seed` caps at `MAX_PHOTO_BYTES` (12 MiB) — `src/kimcad/webapp.py:1410`. A sketch (often a line drawing or phone photo of paper) is plausibly served by the same 12 MiB cap, so the shared constant is reasonable, but the name now under-describes its second use. The 413/400 bodies from `_read_raw_body` are the generic "File too large." / "Empty upload." (`src/kimcad/webapp.py:1771,1774`), whereas the sketch 422 path gives a tailored, on-brand message ("Couldn’t read that sketch — try a clearer image, or cancel and describe the part in words." `src/kimcad/webapp.py:1414`). The oversize/empty messages are generic by comparison.
**Why it matters:** Cosmetic/maintainability. A future reader may not realize `MAX_PHOTO_BYTES` also bounds sketches; the generic oversize copy is acceptable but less helpful than the sketch-specific 422 copy.
**Fix path:** Optional — rename to `MAX_IMAGE_BYTES` (or add a comment at `src/kimcad/webapp.py:57` noting it bounds both photo and sketch uploads). The shared 413/400 copy is fine to leave as-is; if polishing, the maker-facing 422 already covers the common failure.

### FINDING-004 Nit: `_post_sketch`/`_post_photo` test helpers are near-identical copies
**Dimension:** Tests
**Evidence:** `_post_sketch` (`tests/test_webapp.py:2653`) is a verbatim copy of `_post_photo` (`tests/test_webapp.py:2573`) differing only in the URL path. Likewise the unreadable/empty-seed `FakeProvider` subclasses are duplicated per on-ramp.
**Why it matters:** Pure test-hygiene; no functional impact. A third image on-ramp would make the duplication worth factoring.
**Fix path:** Optional — a small `_post_image(path, ...)` helper the two wrap. Not worth doing for two call sites.

## What's working
- **The refactor preserves the photo path exactly.** The diff (`git diff src/kimcad/llm_provider.py`) shows the old `describe_photo` body moved verbatim into `_describe_image` — the `urlsplit`-based native `/api/chat` URL derivation (`src/kimcad/llm_provider.py:312-317`), `{constraints}` substitution, `think: false`, `options` (temp 0, num_predict 400), and the empty-seed stderr breadcrumb (`:346-352`) are all unchanged. `describe_photo` (`:354-361`) delegates with its original prompt name and user message, so there is no behavioral regression. The only wording changes are "photo"→"image" in the shared comment/breadcrumb, which is correct now that the helper serves both.
- **The shared helper means the photo native-chat test still covers the sketch plumbing.** `test_llm_describe_photo_uses_native_chat_with_think_false` (`tests/test_webapp.py:2705`) calls `describe_photo`, which now routes through `_describe_image` — so the native-endpoint/think:false/image-attached wiring that the sketch path also depends on remains pinned (just not under a sketch-named test). This blunts the native-chat half of FINDING-001 to a "name parity" nicety rather than a true coverage hole.
- **Trust boundary is correct in code.** `_SettingsAwareProvider.describe_sketch` (`src/kimcad/webapp.py:464-470`) builds a dedicated LOCAL `LLMProvider(config.llm_backend("local"))` and never touches `_active()` / the cloud cache — identical to `describe_photo`. A sketch cannot auto-send to the cloud even with cloud text fully enabled. The seed is returned as plain text the user confirms; it pre-fills the prompt and still flows through the validated DesignPlan (the route persists nothing).
- **`/api/sketch-seed` robustness mirrors the photo route faithfully.** `_handle_sketch_seed` (`src/kimcad/webapp.py:1405-1427`): 413 (oversize) + 400 (empty) via the shared `_read_raw_body` guard; a broad `except` around the vision call → clean 422 with a maker-friendly message (never a 500, no traceback leak); empty/whitespace seed → 422; nothing written to disk. The 422 body is static copy with no path or secret content.
- **Contract is total and the contract test will catch a miss.** `describe_sketch` is on the `Provider` Protocol (`src/kimcad/llm_provider.py:115-120`), `FallbackProvider` (`:465-468`, delegates via `_call`), `DemoProvider` (`src/kimcad/webapp.py:351-357`, canned seed WITH dims), `_SettingsAwareProvider` (`:464-470`), and `FakeProvider` (`tests/conftest.py:171-174`). `test_all_real_providers_implement_the_full_contract` (`tests/test_pipeline_backends.py:187-200`) now includes `describe_sketch` in its `image` tuple and binds the signature on every real provider — I verified each class has the method, so a future provider that forgets it fails this test.
- **The sketch system prompt is well-targeted.** `system_sketch_seed.md` correctly distinguishes a sketch from a photo: it instructs the model to READ labeled dimensions and use the exact numbers (the maker's intent, not a guess), to say so when a label is illegible rather than inventing a number, to estimate only when there are no dimensions, to map labels to the right axis, to describe ONE part (ignore title blocks/notes), and explicitly frames the output as a STARTING POINT the user confirms — directly addressing HUNT item (8) about not misleading a maker. It carries the `{constraints}` placeholder the helper substitutes (verified present).
- **`describe_sketch` wrapper is correctly differentiated.** It selects `system_sketch_seed.md` and a sketch-specific user message ("Read this sketch of a part to 3D-print: its shape and any labeled dimensions.") — `src/kimcad/llm_provider.py:363-371` — distinct from the photo wrapper, so the dimension-reading behavior is actually wired, not just documented.
- **Tests assert the dimension-bearing seed, not just happy path.** `test_sketch_seed_returns_a_seed_with_dimensions` asserts `"mm" in d["seed"].lower()` and that local vision ran once (`tests/test_webapp.py:2678-2680`); the failure-direction tests assert 422 with "sketch" in the message and 422 on an empty seed. The `FallbackProvider` delegation test asserts the alt is NOT called on primary success (`tests/test_fallback_provider.py:118`).

## Watch items
- When the FRONTEND slice for the sketch on-ramp lands, re-check that the UI labels this an editable starting seed (not a finished part) and surfaces the "couldn't read that sketch" 422 gracefully — the backend copy is good; the UI must not over-promise. (Out of scope for this backend slice.)
- `MAX_PHOTO_BYTES` is now overloaded across two on-ramps; if a third image entry point appears, rename it (FINDING-003) before the name becomes actively misleading.

## Escalation recommendation
No escalation needed. This is a small, well-bounded slice with one Major (a test-coverage gap on a load-bearing invariant) and three low-severity items — squarely in audit-lite's lane. The single Major is a missing test, not a correctness or security defect, and the fix is purely additive. Add the sketch trust-rule test (FINDING-001) and, ideally, the 413/400 sketch tests (FINDING-002) before merge to bring coverage to parity with the photo on-ramp; the rest are optional polish. A full audit-team run is not warranted.

---

## Remediation (maintainer, 2026-06-06) — 0/0/0/0/0

- **FINDING-001 (Major) — FIXED.** Added `test_sketch_never_routes_to_cloud_even_when_cloud_enabled`
  (test_webapp.py) — the load-bearing trust-rule twin of the photo test: cloud TEXT fully enabled,
  a spy `LLMProvider`, and a `_no_active()` guard that asserts `describe_sketch` never consults the
  cloud-capable `_active()`; asserts the LOCAL backend was used and `custom_openrouter` was not.
- **FINDING-002 (Minor) — FIXED.** Added `test_sketch_seed_oversized_is_413` and
  `test_sketch_seed_empty_upload_is_400` (the latter also asserts vision is never invoked on an
  empty body), via the existing `_post_sketch` helper.
- **FINDING-003 (Minor) — FIXED (comment).** `MAX_PHOTO_BYTES` now documents that it caps BOTH
  image on-ramps (photo + sketch); a rename was deemed not worth the ripple.
- **FINDING-004 (Nit) — ACCEPTED.** `_post_sketch` mirrors `_post_photo`; not worth factoring for
  two call sites.

Re-verified: ruff clean; the 7 sketch/trust tests pass; full non-live suite green.
