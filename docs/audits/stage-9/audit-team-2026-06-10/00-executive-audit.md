# Stage 9 stage gate — Executive audit (audit-team, 2026-06-10)

**Scope:** the Stage 9 diff (`574b7c4..e8339d9` on `main`) — Slice 1 (sketch backend), Slice 2
(sketch UI), Slice 3 (vision-model fix + benchmark + docs), and the `DesignRegistry` extraction.
All five roles, balanced posture, writer audit-only. Deep-dives: `01`–`05` in this directory.

**Verdict at audit time: 0 Blocker / 0 Critical / 10 Major / 18 Minor / 5 Nit (33 findings).**
**Verdict after remediation (same day): 0/0/0/0/0 — every finding fixed and re-verified** (see
the Remediation record below). Per the project's standing rule, all severities were remediated,
not just the punch-list tiers.

## Executive summary

Stage 9 shipped the right thing the hard way: it *measured* the inherited photo on-ramp against
the real pinned model, found gemma4:e4b's vision broken on this stack (a Critical product defect
that had been masked by demo mode since Stage 8.5), fixed it with a dedicated local vision model,
and recorded the photo→3D descope honestly against ROADMAP's own exit criterion. The sketch path
works end-to-end against the real model (verified live in the walkthrough). The engineering
seams are sound — the `DesignRegistry` extraction preserved all three locking protocols — but the
gate found real gaps at the edges: a non-404 vision error blamed the user's image, the
"local-only" promise was enforced by convention rather than structure, the wizard could say
"Ready" while the on-ramps were doomed, the dual on-ramps never actually rendered side by side,
and the doc set still carried the disproven "gemma reads images" claim in four authoritative
places. Nothing found blocks the stage; everything found was fixed before the tag.

## Severity roll-up (at audit time)

| Role | Blocker | Critical | Major | Minor | Nit |
|---|---|---|---|---|---|
| 01 Engineering | 0 | 0 | 1 (ENG-001) | 3 | 1 |
| 02 UI/UX | 0 | 0 | 2 (UX-901, UX-902) | 6 | 2 |
| 03 Documentation | 0 | 0 | 4 (DOC-001..004) | 4 | 0 |
| 04 Test | 0 | 0 | 3 (TEST-001..003) | 3 | 2 |
| 05 QA | 0 | 0 | 0 | 2 | 0 |
| **Total** | **0** | **0** | **10** | **18** | **5** |

## Top findings (all remediated)

1. **ENG-001 (Major)** — a 5xx/429 from Ollama during a vision read fell into the generic
   handler and told the user their image was unreadable, logging nothing.
2. **UX-902 (Major)** — the wizard advertised the vision model but never checked it; "You're
   all set" could be a lie for the on-ramps. `/api/model-status` had no vision fields.
3. **UX-901 (Major)** — the Stage-8.5 `.kc-photo-landing { width:100% }` defeated the new
   `.kc-onramps` flex row; the "side by side" on-ramps always stacked (verified live).
4. **DOC-002 (Major)** — the design control plane ("Build to this") still asserted gemma4:e4b's
   vision as a settled decision — the exact claim Stage 9 measured false.
5. **DOC-001 (Major)** — the Settings guide said KimCad runs "one tested local model"; a user
   diagnosing an image failure from it would never find the missing second model.
6. **TEST-002 (Major)** — the lockstep-eviction test excluded `meshes`, hiding a fail-open seam
   (the slice gate treats a missing verdict as not-failed).
7. **TEST-001 (Major)** — `uploadSketch`'s whole client transport contract was untested.
8. **TEST-003 (Major)** — the webapp's transitional alias seam was only partially pinned.
9. **DOC-003 / DOC-004 (Major)** — the sketch feature had no user guide; CHANGELOG owed the
   Stage 9 entry including the correction of the 8.5 photo claim.
10. **ENG-002 (Minor, security)** — "images never leave the machine" was enforced only by
    routing convention; nothing structural refused a non-local host.

## What's working well (credit where due)

- **The benchmark discipline** (`docs/benchmarks/stage-9-vision-onramps.md`): a shipped-feature
  defect found by measurement, isolated with a split test, fixed, and re-measured end-to-end —
  with the descope verdict argued from hardware facts. All five roles independently verified its
  claims against code and found them true.
- **The trust boundary held everywhere it was probed:** images never persisted, never logged,
  never routed to the cloud provider; the seed flows into the same validated DesignPlan schema.
- **`DesignRegistry`** preserved all three locking protocols through the extraction, with the
  `_locked` contract documented and the transitional alias seam explicitly scheduled
  (Stage-10-start) rather than left ambient.
- **Error-copy ↔ troubleshooting contract:** typed error strings match doc headings verbatim —
  a user can paste the error into search and land on the fix.

## Remediation record (all 33 → fixed, same day, this package's addendum)

| Finding | Fix |
|---|---|
| ENG-001 | `VisionReadError` (carries the HTTP code): 404 → `VisionModelMissing`, any other `HTTPError` → friendly try-again; both image endpoints map it to typed `model_unavailable` JSON and `log_error` the code. Negative test TEST-004 added. |
| ENG-002 | Structural loopback-only guard in `_describe_image` — a non-local host raises before any request is built; pinned by a test using a cloud backend. |
| ENG-003/ENG-005 | Dead `_evict` alias removed; slice handler reads `reg.version_locked(rid)`. |
| ENG-004 | Registry docstrings name only real methods; the GIL/atomicity claim replaced with the lock-is-the-guarantee statement. |
| UX-901 | Scoped `.kc-onramps` overrides (idle on-ramp shrinks; `:has(.kc-photo-card)` takes the row). Verified live: same-row at desktop, clean wrap at 375, workspace pair same-row. |
| UX-902 | `/api/model-status` gains `vision_model` + `vision_present` (local backend; honestly omitted for cloud, where it can't be probed); wizard model step gains a vision action line with re-check; `ModelHealthPill` warns when only the vision model is missing ("designing in words works now"). |
| UX-903 | Confirm-card title names the source: "A rough starting point — from your photo/sketch". |
| UX-904 | `VisionModelMissing` copy de-jargoned (plain "isn't downloaded yet… In a terminal, run:"). |
| UX-905 | Wizard welcome: "or start from a photo or a sketch". |
| UX-906 | Error message gets `tabIndex={-1}` + focus on entering the error phase. |
| UX-907 | Workspace gains the sketch on-ramp beside the photo one (`.kc-onramps-workspace`). |
| UX-908 | Model-card vision sentence rewritten plain ("A second small download lets KimCad read photos and sketches"). |
| UX-909 | Error group label neutral ("Something went wrong reading your …"). |
| UX-910 | "— or drop an image here" hint on both affordances (hidden on coarse pointers). |
| DOC-001 | Settings guide: two tested local models + which to check when images fail. |
| DOC-002 | Stage-9 correction blocks added to `docs/design/README.md` banner (+ tech table row), the spec's CONTROL-PLANE banner (item 2a) + §6.10/§7.2 inline notes; `stage-8.5-usability-plan.md` reclassified Historical in `docs/README.md`. |
| DOC-003 | `guide-photo-onramp.md` extended to both on-ramps (retitled; "Photos vs. sketches" section; drag-drop, caps, cancel); index line updated. |
| DOC-004 | CHANGELOG Stage 9 entry written (requirements change first; corrects the 8.5 vision claim explicitly). |
| DOC-005 | ROADMAP status ¶ + Stage 9 ✅ EXIT MET block (descope branch recorded); README status ¶; HANDOFF resume box. |
| DOC-006 | Harness committed (`scripts/bench_vision.py`) + "How to re-run" section in the benchmark doc; sanity probe re-run live to verify the committed harness reproduces Finding 2. |
| DOC-007 | getting-started: 15 GB → 20 GB ("the two AI models"). |
| DOC-008 | ARCHITECTURE.md: `design_registry.py` module row + Stage 9 additions paragraph (`/api/sketch-seed`, `vision_model` mechanics, typed failures, model-status vision fields). |
| TEST-001 | Five `uploadSketch` transport tests (endpoint, cap, abort, 422, `model_unavailable`). |
| TEST-002 | `evict_locked` pops `meshes` (fail-closed); test asserts it. |
| TEST-003 | Alias pins extended: post-eviction `/api/mesh/<id>` + `/api/step/<id>` → 404, save-of-evicted → 4xx. |
| TEST-004 | Non-404 `HTTPError` → `VisionReadError` (and explicitly NOT `VisionModelMissing`) test. |
| TEST-005 | `kimcad models` vision line asserted in both installed and not-installed wordings. |
| TEST-006 | Registry edge tests: never-registered evict, double-evict idempotence, slice-cache cap eviction. |
| TEST-007/008 | Docstring phantom method fixed; trailing newline restored; dead alias removed. |
| QA-901 | `_ExclusiveBindServer.handle_error` suppresses client-disconnect tracebacks (one quiet line). |
| QA-902 | Documented limitation (comment at the read site): an aborted read can't cancel the in-flight Ollama generation; the retry queues behind it. Accepted for Stage 9 — revisit if reads lengthen. |

**Re-verification after remediation:** ruff clean; **929 pytest** passed; **313 vitest** passed
(25 files); `tsc -b` clean; SPA rebuilt and committed; UX-901/907 re-checked live in the demo
preview at 375 px and desktop widths; the committed benchmark harness re-run live (sanity probe
read the labeled image correctly through qwen2.5vl:3b).

## This-sprint punch list

See `sprint-punchlist.md`. All items were executed in this remediation pass (0/0/0/0/0).

## Next-sprint watchlist

See `next-sprint-watchlist.md` — the forward-looking items (alias flattening at Stage-10-start,
the QA-902 abort limitation, Settings vision row, wizard model-pull-with-progress).

## Blast-radius notes

- **`/api/model-status` payload grew** (`vision_model`, `vision_present`). Optional fields;
  existing consumers unaffected. The cloud path intentionally omits `vision_present` — UIs must
  treat absence as unknown, never as missing.
- **The on-ramp CSS overrides are scoped to `.kc-onramps`** — the standalone
  `.kc-photo-landing`/`.kc-photo-workspace` rules still govern any future solo use.
- **`ChatPanel` now renders two on-ramps** — tests that queried the single workspace on-ramp by
  role/name still pass because names differ per kind.
- **The control-plane banners were corrected, not rewritten** — historical text below them is
  unchanged; future stages that overturn settled decisions must sweep the banners again
  (systemic note in `03`, worth institutionalizing).
