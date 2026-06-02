# Stage 5 — Sprint Punch List (0/0/0/0/0 gate)

Every finding is in-sprint (the gate requires all fixed). Owner hint = the role that surfaced it. Size: S (≤30 min) / M (≤2 h) / L (>2 h).

## Major

| ID | Title | Role | What to do | Size |
|---|---|---|---|---|
| DOC-001 | HANDOFF.md stale (head/count/next-step/test-count) | Docs | Rewrite the Stage 5 section: head `91b691c`, 8 ahead, Slices 1–5 done, next = the stage gate; single-source the 484 count; retitle. | M |
| TEST-001 | No test: gate-FAILED re-render → non-sliceable/non-sendable | Test | Add `test_rerender_into_a_gate_failed_shape_blocks_slice_and_send` (force build-volume overflow → gate fail → slice + send refused) + a unit companion. | M |
| TEST-002 | Frontend `renderSeq` stale-response discard untested | Test | Add an `App.test.tsx` case: two deferred `postRender`s, resolve the older last, assert the newer result wins. | M |

## Minor

| ID | Title | Role | What to do | Size |
|---|---|---|---|---|
| ENG-501 | `wall_hook` bbox under-reports Z by 2 mm at `plate_h` min | Eng | Raise `plate_h` min 20→24 in the ParamSpec; add a `plate_h=min` analytic==actual test. | S |
| ENG-502 | `version_counter` read outside `lock` | Eng | Move `next(version_counter)` inside the `with lock:` block. | S |
| ENG-503 | `render_lock` process-global | Eng | Add a `# single global lock: fine for the single-user local UI` note; per-id lock deferred to multi-client work. | S |
| UX-001 | Mobile slider touch target < 44 px | UI/UX | Add `.kc-range` to the coarse-pointer 44 px rule + a transparent 44 px hit area (padding + `background-clip`), keep the 9 px painted track. | S |
| UX-002 | Re-render error copy leaks the raw message | UI/UX | Lead with a human sentence that reassures the last version is intact; demote the raw detail. | S |
| UX-003 | "Updating…" note has no minimum dwell (flicker) | UI/UX | Give the in-flight note a small minimum visible duration so it reads as deliberate. | S |
| DOC-002 | HANDOFF "Slice 4 pickup" describes committed work | Docs | Replace the Slice-4/5 pickup blocks with the remaining gate steps (folds into DOC-001). | S |
| DOC-003 | Benchmark "Generated" date predates its mtime | Docs | Regenerate with the real date (`--date 2026-06-01`). | S |
| DOC-004 | CHANGELOG "<1 s" reads as the enforced bar | Docs | Reword to "measured 0.13–0.45 s per family (interactive target <1 s; CI gate ≤5 s)". | S |
| TEST-003 | "<1 s" never asserted on a real render | Test | Add `assert report.all_meet_target` to the live bench gate (margin is 2–7×). | S |
| TEST-004 | Debounce fire-after-unmount untested | Test | Add a RightPanel test: change a slider, unmount, advance timers, assert `onRerender` not called. | S |
| TEST-005 | Two concurrency tests timing-sensitive | Test | Harden `test_concurrent_rerenders_are_serialized` to a "inside-render counter never > 1" invariant (jitter-free). | S |
| QA-001 | Build-volume gate-fail unreachable via demo template | QA | No code change (safe by design); TEST-001's forced-overflow test gives the gate-fail path a reachable runtime exercise. | S |
| QA-002 | `/api/render` conflates unknown-id vs LLM-backed 404 | QA | Split: unknown id → "Design not found."; known-no-template → "no adjustable parameters." | S |

## Nit

| ID | Title | Role | What to do | Size |
|---|---|---|---|---|
| ENG-504 | `_singular` plural-stripping fragile for future aliases | Eng | Add a test asserting `_singular` over all aliases yields no cross-family collision. | S |
| ENG-505 | `derive_values`/`clamp_values` duplicate coerce/clamp/gaps tail | Eng | Extract a `_finalize(family, raw)` helper both call. | S |
| ENG-506 | `DemoProvider.generate_openscad` dead in demo mode | Eng | One-line comment: the template tier shadows it in demo mode. | S |
| ENG-507 | `template_bench._perturb` assumes `params[0]` affects geometry | Eng | Document the assumption in the `_perturb` docstring. | S |
| UX-004 | Sliders dropped the prototype's per-axis W/D/H chip | UI/UX | Expose `bbox_axis` in the param payload + restore the `.kc-axis` chip. | M |
| UX-005 | LLM read-only note is insider-y, doesn't point forward | UI/UX | Reword "written by the model" → "generated directly"; keep it honest. | S |
| UX-006 | "Updating…" vs subtitle "under a second" vocabulary | UI/UX | "Updating…" → "Re-rendering…". | S |
| UX-007 | Confirm `:focus-visible` doesn't fire on pointer-drag | UI/UX | Verification-only (code correct by construction); confirm in a manual Tab-vs-mouse pass. | S |
| DOC-005 | ARCHITECTURE library count cross-reference | Docs | Verified clean — no action. | S |
| DOC-006 | HANDOFF dated title carries stale phase label | Docs | Folds into DOC-001 (retitle). | S |
| TEST-006 | `/api/render` 404 conflation test gap | Test | Add the unknown-id 404 assertion (pairs with QA-002). | S |
| TEST-007 | Viewport reload on `?v=` only indirectly asserted | Test | Accepted no-browser-E2E boundary; api-test covers `?v=` stripping. Optional viewport harness later. | S |
| QA-003 | Slice-failure `note` leaks a raw process error | QA | Normalize the exit code to signed + a plain-English hint when stderr is empty. | S |
| QA-004 | Generic 404 bodies ("not found") terse vs the friendly ones | QA | Standardize the generic 404 copy to the friendly sentence voice. | S |
