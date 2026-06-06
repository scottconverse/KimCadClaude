# Stage 8 re-audit — UI/UX + Documentation lanes (closure)

**Re-audit date:** 2026-06-06
**Reviewer posture:** independent, skeptical (re-audit of remediation, working tree uncommitted)
**Branch:** `stage-8-cadquery` (HEAD `b945569`)
**Scope:** the UX-001..007 and DOC-001..007 findings from `02-uiux-deepdive.md` /
`03-documentation-deepdive.md`, plus the standing honesty checks (no `stage-8` tag; OS-confinement
deferral documented). Verified against source, the shipped web bundle, and a LIVE rendered demo.
**Tooling:** source read; `git`; shipped-bundle CSS/JS grep; a self-started demo server
(`:8782`, OpenSCAD/Python-3.14) driven via the API; and a real rendered browser session via the
preview harness (`:8765`) — DOM, computed styles, and measured contrast.

---

## Verdict roll-up

| Lane | CLOSED | Accepted (house style / deferred, documented) | New findings |
|---|---|---|---|
| UX (UX-001..007) | UX-001, UX-002, UX-003, UX-005, UX-006 | UX-007 | **UX-N1 (Minor)** — STEP-link contrast on its new pill |
| UX-004 | CLOSED (meets ≥40px brief target) | — | (see note) |
| DOC (DOC-001..006) | DOC-001, DOC-002/003, DOC-004, DOC-005 | DOC-006 | none |
| Honesty / Stage-11 | CLOSED | — | none |

**Overall: SHIP (UX + docs lanes), with one new Minor (UX-N1) to log.** No Blocker/Critical/Major
open in either lane. The one new item is a sub-AA contrast on the STEP download text introduced by
the UX-003 pill; it is cosmetic, on a source-only (non-demo) state, and does not gate ship.

---

## Rendered check (the required live verification)

Demo design "a 40 mm desk cable clip" built an OpenSCAD part (80×60×40 mm box), gate **Passed**.

- **Engine chip renders.** The Printability card shows, in the gate row: `Gate: Passed` (green
  pill) + `Engine: OpenSCAD` (neutral bordered pill). Confirmed in the DOM *and* in a screenshot.
  Driven by `report.backend` — the API response carried `report.backend == "openscad"`,
  `step_url == null` (correct for OpenSCAD).
- **Chip is visually distinct from the gate badge.** Computed styles differ on every axis:
  color (`rgb(111,104,87)` muted vs `rgb(29,122,78)` green), background (cream pill
  `rgb(244,238,226)` vs green tint), weight (600 vs 700), border (1px vs none).
  `sameColor/sameBg/sameWeight` all false.
- **Engine-chip contrast = 4.79:1** (text `rgb(111,104,87)` on its pill bg `rgb(244,238,226)`) —
  **passes WCAG AA** for normal text (≥4.5:1). Formats note 5.14:1 (pass).
- **Reworded formats note renders** (OpenSCAD branch), verbatim: *"…KimCad picks the geometry
  engine to fit each part (shown on the printability check above); parts built with the precision
  CAD engine (CadQuery) also offer an editable .STEP export."* No phantom control; points to the
  chip; uses "precision CAD engine (CadQuery)".
- **`.kc-download-model` min-height shipped & applied:** computed `min-height: 40px`, rendered
  height 40.0px, padding `8px 2px`, `display:flex`. `.kc-formats` gap `8px`. Present in
  `/assets/index.css` (served live).
- **`.kc-download-step` shipped:** present in `/assets/index.css`. Verified the rule actually
  applies by injecting a transient node with the STEP classes into the live page (removed
  immediately, no source touched): it gets a bordered 8px-radius cream pill, `padding-left/right:
  10px`, and the `::before` edit glyph `"✎"` — clearly distinct from the STL link (no border,
  transparent bg, 2px padding). All three distinctness checks true.

The STEP-PRESENT card state needs a CadQuery part (not producible on the 3.14/OpenSCAD demo), so
the STEP link's *appearance* was assessed from source + the shipped CSS + the live class-injection
above, consistent with the prior pass.

---

## UX findings — per-item

### UX-001 — CLOSED
Neutral `Engine: CadQuery / OpenSCAD` provenance chip on the Printability card.
`RightPanel.tsx:548-557` renders `<span className="kc-engine-badge">` gated on `report.backend`,
in the gate row next to the gate badge, with a descriptive `title`. CSS `.kc-engine-badge`
(`styles.css:3271`) is a muted neutral bordered pill, shipped to `/assets/index.css`. Data flows
`api.ts:49 report.backend` → component → DOM. **Rendered-verified ("Engine: OpenSCAD").** Tests
assert both values (`RightPanel.test.tsx:133/139`). The STEP affordance is no longer the only
(inferred) engine signal.

### UX-002 — CLOSED
No-STEP formats note no longer dead-ends. `ExportPanel.tsx:204-212`: states KimCad picks the
engine to fit each part, points to the printability check (where the chip lives), names the
precision CAD engine, and explains STEP is for CadQuery parts — no phantom control implied.
Rendered-verified.

### UX-003 — CLOSED
`.kc-download-step` now has a distinct treatment: leading edit glyph (`::before content:"✎"`) +
bordered cream pill (`styles.css:1748-1761`), shipped to `/assets/index.css`. Live class-injection
confirmed it renders distinct from the STL link. **See UX-N1** for a contrast side-effect.

### UX-004 — CLOSED (meets brief)
`.kc-download-model` now `min-height:40px` + `padding:8px 2px`; `.kc-formats` `gap:8px`
(`styles.css:1728-1739, 1855-1860`), shipped. Rendered height 40.0px. The brief target was
"≥40px"; met. (Note: WCAG 2.1's *ideal* is 44×44; 40px is the agreed fix and the deep-dive
flagged the 44px shortfall as a pre-existing pattern amplified by Stage 8, not introduced by it.
Not re-opening — meets the stated bar.)

### UX-005 — CLOSED
STEP-present note (`ExportPanel.tsx:196-203`) leads with downloadable-now (`.STL`, then `.STEP`)
and gates `.3mf` behind "Once you slice." Source-verified (STEP-present state not demo-producible).

### UX-006 — CLOSED
"the CadQuery engine" → "the precision CAD engine (CadQuery)" in both note branches
(`ExportPanel.tsx:199, 209`). Rendered-verified in the OpenSCAD branch.

### UX-007 — ACCEPTED (house style, verified consistent)
On-disk file lowercase `.step` (`cadquery_runner.py:202`); download filename lowercase
`kimcad-part-{sid}.step` (`webapp.py:961`); UI label uppercase `.STEP` (`ExportPanel.tsx:193`).
Format-name-uppercase / file-lowercase is the documented convention and is internally consistent.

### UX-N1 — NEW — Minor — Accessibility (contrast) — STEP-link text dips below AA on its new pill
The UX-003 pill gives `.kc-download-step` a cream background (`rgb(244,238,226)` via
`--kc-surface-2`). The STEP link text is the terracotta accent `rgb(177,84,47)`. Measured contrast
on the pill = **4.35:1**, just under the 4.5:1 AA threshold for normal text (the link is 12.5px /
weight 600 — not large-text, which would need 18.66px or 14pt-bold). On the page surface the same
text was ~4.66:1 (AA pass, per the prior deep-dive), so the new pill *background* slightly lowered
it. Cosmetic and on a non-demo state, but it is a real, measurable AA regression *introduced by the
remediation*. Fix path: darken the STEP link text on the pill (e.g. use `--kc-accent-strong`'s
darker stop, or a slightly darker pill-specific accent) to clear 4.5:1, or lighten the pill less.
Does not gate ship; log for the next polish pass.

---

## DOC findings — per-item (verified against source)

### DOC-001 — CLOSED (all four sites consistent)
The worker `__import__` is now described as returning the facade for `cadquery`, real `math`, AND
**raising `ImportError` for any other import**, matching `_safe_import` (`cadquery_worker.py:91-97`)
verbatim, in all four places:
- `docs/cadquery-backend.md:79-82`
- `cadquery_worker.py:33-37` docstring
- `CHANGELOG.md:45-47`
- `ARCHITECTURE.md:79`

Supporting tests exist at the worker layer (`test_worker_withholds_dangerous_builtins_beyond_open`,
`test_worker_facade_has_no_module_pivot_to_os`, the parametrized
`test_render_cadquery_blocks_escape_class_end_to_end`) — all `@pytest.mark.live` (skip without a
CadQuery interpreter, as in this 3.14 env). Minor observation, NOT a doc defect: there is no test
that asserts a bare `import os` raises `ImportError` *specifically at the worker* (`_safe_import`);
the import boundary is covered by the sanitizer-level `test_disallowed_import_is_blocked` and the
end-to-end escape suite, and the worker source plainly raises it. The doc accurately describes the
code; a one-line worker-level `import os` test would make the claim self-evident (optional).

### DOC-002 / DOC-003 — CLOSED
`docs/cadquery-backend.md:40-43` "Enabling it" now restates the no-3.14-wheels reason and notes a
3.11–3.13 KimCad install can host CadQuery **in place** ("no second Python required. Only a 3.14
KimCad install needs a separate ≤3.13 interpreter").

### DOC-004 — CLOSED (scoped)
"every *top-level* cadquery submodule is stripped" in `cadquery-backend.md:82`,
`cadquery_worker.py:37`, `CHANGELOG.md:47`, `ARCHITECTURE.md:79`. Matches `_build_facade`
iterating `vars(cadquery)` (`cadquery_worker.py:79`).

### DOC-005 — CLOSED
Bench doc (`benchmarks/stage-8-cadquery-backend.md:34-38`) marks the cadquery/OCP versions as
"as-measured environment, **not** a version requirement" and states the sorted-dims (orientation-
invariant) tolerance scope, pointing to `test_render_cadquery_builds_a_box` as the tight per-axis
check. The union-lift remains correctly hedged (lines 60-62, honesty note).

### DOC-006 — ACCEPTED (house style; same as UX-007)
STEP = format name (uppercase in prose/UI), `.step` = on-disk/download extension (lowercase).
Convention is stated and consistent.

---

## Honesty / status re-confirmation (still holds)

- **No `stage-8` tag.** `git tag` → `stage-0..7` + `stage-8.5`; NO bare `stage-8`. Branch is
  `stage-8-cadquery`, not on `main`.
- **No doc claims Stage 8 done/merged/tagged.** README/ROADMAP/CHANGELOG/ARCHITECTURE all say
  "BUILT (branch `stage-8-cadquery`; stage gate + merge + tag pending)" / "next step." Consistent.
- **OS-confinement deferral documented as Stage 11**, not silently dropped:
  `cadquery-backend.md:97-99`, `cadquery_worker.py:48-50`, `CHANGELOG.md:50`, `ARCHITECTURE.md:79`.
  The in-tree mitigations (secret-scrubbed env, isolated cwd) are stated as the interim.

---

## Regression / wiring checks

- Component tests pass: `vitest run RightPanel.test.tsx ExportPanel.test.tsx` → **55/55 passed**.
  They assert the engine chip (both values) and the reworded notes — the fixes are wired, not just
  present in source.
- Frontend typecheck clean: `tsc --noEmit` → exit 0.
- Shipped bundle is in sync: `/assets/index.css` and `Workspace.js` carry `kc-engine-badge`,
  `kc-download-step`, `min-height:40px`, "Engine:", and "precision CAD engine" — the built bundle
  matches the source fixes (no stale-bundle drift).
- No malformed CSS comments (the apparent `\*` in tool output was a display artifact; on-disk is
  `/* */`).

## Git cleanliness

`git status --porcelain`: the only untracked entry is
`docs/audits/stage-8/audit-team-stage-8-2026-06-06/`. The 18 modified files are the remediation set
(unchanged by this re-audit). **I made no edits to any repo file.** Temp experiment artifacts were
written outside the repo; the live DOM class-injection was transient (removed in the same eval).
My demo server on `:8782` was stopped and the port freed.
