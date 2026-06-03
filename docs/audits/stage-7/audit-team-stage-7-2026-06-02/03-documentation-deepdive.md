# Stage 7 Audit — Documentation Deep-Dive

**Role:** Technical Writer (audit-only, balanced posture)
**Stage:** 7 — Smart Mesh + PrintProof3D + readiness report + learning store
**Branch:** `stage-7-smart-mesh` (verified: not merged, no `stage-7` tag, working tree clean)
**Date:** 2026-06-02
**Scope:** CHANGELOG.md, ROADMAP.md, README.md, ARCHITECTURE.md, HANDOFF.md,
`docs/printproof3d-integration.md`, `config/default.yaml` — the Stage-7 doc edits, checked for
accuracy / completeness / honesty / internal-consistency against the source.

---

## Verdict

**The Stage-7 documentation is honest and accurate.** The load-bearing check passes cleanly: **no
doc claims Stage 7 is done, merged, or tagged.** Every Stage-7 status line in the four product-facing
docs and the new engine doc frames the stage as *implemented on `stage-7-smart-mesh`, pending the
stage-end `audit-team` gate, not yet merged or tagged.* That framing is consistent across files and
matches the actual repo state. Every doc claim I spot-checked against the code held up — including
the subtle ones the brief flagged (advisory-not-blocking, `~`-no-expansion, off-by-default, never-raises,
worst-of-two tone, High/Medium confidence, attribution strings).

Findings are all **Minor / Nit**. No Blocker, Critical, or Major. The honesty discipline that was
missing in the Stage-4 incident is visibly present here.

---

## Severity counts

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 2 |
| Nit | 2 |
| **Total** | **4** |

---

## The load-bearing check (status honesty) — PASS

Ran `git grep -niE "stage.?7|smart mesh|printproof"` across all seven files and inspected every
"tagged / merged / done" adjacency:

- **CHANGELOG.md** — `[Unreleased]` header note (lines 12–14) and the `#### Stage 7` subsection
  (line 218) both read "implemented on `stage-7-smart-mesh` and pending its stage-end `audit-team`
  gate — not yet merged or tagged." The Stage-7 block sits under `[Unreleased]`, **untagged**, exactly
  as required. The "merged + tagged" language at lines 9–11 and 20 is correctly scoped to **Stages
  5–6**, not Stage 7. ✅
- **ROADMAP.md** — "Current baseline" (lines 54–56), "Still ahead" (line 58), and the Stage 7 section
  status line (lines 182–184) all say "IMPLEMENTED on `stage-7-smart-mesh` … pending its stage-end
  `audit-team` gate — not yet merged or tagged." ✅
- **README.md** — line 40: "*(Stage 7 — implemented on the `stage-7-smart-mesh` branch, pending its
  stage gate.)*" ✅
- **ARCHITECTURE.md** — the three module rows (lines 99–101) describe behavior, not status, and make
  no done/tagged claim. ✅
- **HANDOFF.md** — title and status block (lines 1, 5, 36–39) say "STAGE 7 IN PROGRESS … NOT merged …
  REMAINING = the stage-end `audit-team` gate … → merge → tag `stage-7`." ✅
- **docs/printproof3d-integration.md** — `git grep` for done/complete/finished/merged/tagged/shipped/
  released returned **zero hits**. ✅
- **config/default.yaml** — comments only; no status claims. ✅

**Conclusion:** the document set does not overclaim Stage-7 completion anywhere. This is the dimension
the project was burned on before, and it is correct here.

---

## Code-vs-doc claim verification — all claims confirmed

Each Stage-7 doc claim the brief called out was checked against the source. Result: **no overclaims.**

| Doc claim | Source checked | Result |
|---|---|---|
| CLI `validate-model --model/--printer/--material/-o` | `printproof3d.py` L83–89 | Matches exactly |
| Report schema (status pass/warning/fail; confidence; issues[severity/message/suggested_fixes/location]) | `printproof3d.py` `_parse_report` L106–138; `smart_mesh.py` L38–55 | Matches; doc note "unknown severity → skipped" matches L121 |
| "off by default" | `config.py` `printproof3d_binary()` L116–126 (gates on `p.exists()`) | Accurate — active key in default.yaml resolves to "not present" until a binary exists |
| "never raises / degrades to None" | `printproof3d.py` L68, L80–81, L90–103 | Accurate — every failure path returns `None` |
| "cargo build --release" | engine is external (owner's repo) | Plausible; not verifiable in-repo (expected) |
| advisory; deterministic gate stays slice authority; folding engine fail into gate is a follow-up; enabling engine never changes what slices | `pipeline.py` L429–433, L491–521 (readiness on report, slice gate unchanged); integration doc L78–84 | Accurate — doc frames slice-blocking strictly as a **future follow-up**, never a current capability |
| `paths.history` default `~/.kimcad/history.json`; absolute used as-is; relative → PROJECT_ROOT; **no `~` expansion** of a config value | `config.py` `history_path()` L128–137 (`Path(raw)`, no `expanduser`; `Path.home()` only on the unset default) | Matches precisely |
| `paths.history` block fully commented (no active override of the home default) | `config/default.yaml` L16–21 | Confirmed — entire block commented |
| README/ARCHITECTURE pipeline diagrams agree on readiness placement (after harden, before confirm/slice) | README L22–25; ARCHITECTURE L29–34 | Consistent — both: harden → Smart Mesh readiness → [confirm] slice |
| Config keys `binaries.printproof3d` / `paths.history` match what config.py reads | `config.py` L121, L133 | Match |
| Confidence rises to High + attribution "PrintProof3D validation engine" when engine present; else Medium / "KimCad printability gate" | `smart_mesh.py` `_confidence` L198–205, `_attribution` L208–214 | Matches exactly |
| "worst of two signals" tone | `smart_mesh.py` L158–171 | Matches (`max` over `_TONE_RANK`) |
| Cross-refs exist: `docs/benchmarks/stage-5-template-families.md`, `docs/design/screens/10-smartmesh-report.png` | filesystem | Both present |

---

## Findings

### DOC-001 (Minor) — Source-comment "prints" vs. user-facing "parts" wording drift
**Category:** Accuracy / Internal consistency

**Evidence:** The four product-facing docs correctly say **"compared to your past parts"**
(README.md L37, ARCHITECTURE.md L101, CHANGELOG.md L243, ROADMAP.md L197) — which matches the actual
`compare_phrase()` output, whose wording is **"parts"** (`history.py` L61–66) and is deliberately
chosen ("'Parts' (not 'prints') because the store holds designed parts, some gate-failed and none
necessarily printed," `history.py` L46–48). However, the *source docstrings/comments* still say
**"prints"**: `history.py` L4 ("compared to your past prints"), L9 ("Stronger than 7 of your 9 past
prints"), and `pipeline.py` L437 + L524.

**Why this matters:** The user-facing docs are correct, so no reader is misled. But the source
comments contradict the code's own stated rationale and the example string in the `history.py`
docstring (L9, "past prints") doesn't match what the function actually emits ("past parts"). A future
maintainer reading the docstring could reasonably "fix" the code to say "prints," regressing the
deliberate choice.

**Blast radius:**
- Adjacent code: `history.py` (module docstring + `compare_phrase` docstring example), `pipeline.py`
  (`_apply_history_comparison` docstring L524, comment L437).
- User-facing: none — runtime output and product docs already say "parts."
- Migration: none.
- Tests to update: none (no test asserts the docstring text).

**Fix path:** Out of this audit's doc-edit scope (these are source comments, not the Stage-7 doc
edits). Recommend the Principal Engineer reviewer normalize the four source comments to "parts" so
the code's intent and its comments agree.

---

### DOC-002 (Minor) — HANDOFF carries two different test counts in two sections
**Category:** Accuracy (stale operational doc)

**Evidence:** `HANDOFF.md` L41 states the Stage-7 branch is green at **"664 pytest (incl. live) + 43
vitest."** L110, in an older Stage-6-era section, says **"609 pytest incl. live OrcaSlicer; 37
vitest."** `ROADMAP.md` L37 says **"404 tests passing"** in yet another historical context.

**Why this matters:** These describe different points in the project's history (the L110 / ROADMAP L37
numbers predate the Stage-7 work), so they are stale-in-context rather than a live contradiction. The
risk is low because HANDOFF is operator scaffolding, not user-facing product documentation. But a
reader skimming HANDOFF sees two test totals without an obvious "as of" anchor on the older one.

**Blast radius:**
- Adjacent code: none.
- User-facing: none (HANDOFF and the ROADMAP "Current baseline" prose are internal/operational).
- Migration: none.

**Fix path:** Optional. If touched, tag the L110 figure with its stage ("as of Stage 6") so it reads
as a historical checkpoint, not a competing current count. Not blocking — these counts are inherently
point-in-time and the authoritative gate is the pre-push hook, not a doc number.

---

### DOC-003 (Nit) — `binaries.printproof3d` ships as an *active* key while the doc says "off by default"
**Category:** Accuracy (precision of phrasing)

**Evidence:** `docs/printproof3d-integration.md` L29 — "The engine is **off by default** — the path
is configured but the binary isn't fetched, so KimCad resolves it to 'not present' and degrades."
`config/default.yaml` L14 has an **active (uncommented)** key `printproof3d:
tools/printproof3d/printproof3d.exe`, in contrast to the fully *commented* `paths.history` block
above it (L16–21).

**Why this matters:** The phrasing is technically correct — `Config.printproof3d_binary()` gates on
`p.exists()` (`config.py` L126), so a configured-but-absent path does resolve to `None` / "off."
The doc even explains this precisely at L29 and L45–46. The only nit: a reader diffing the YAML might
briefly wonder why one Stage-7 key is active and the other commented, since both are "optional." The
asymmetry is intentional (the binaries block mirrors `openscad`/`orcaslicer` which are also active
default paths), and the doc's own wording is honest about the behavior.

**Fix path:** None required. If desired, a one-line YAML comment near L14 noting "active path, but
inert until a binary exists at it" would preempt the question. Not a defect.

---

### DOC-004 (Nit) — Screen mockup `10-smartmesh-report.png` is referenced only in HANDOFF, not in the user-facing docs
**Category:** Completeness

**Evidence:** The Stage-7 readiness card design mockup `docs/design/screens/10-smartmesh-report.png`
exists and is referenced in `HANDOFF.md` L8. It is **not** linked from README, ARCHITECTURE, ROADMAP,
or the new integration doc.

**Why this matters:** Barely at all — the card is a UI artifact whose audit belongs to the UI/UX role,
and a screenshot is not expected in an engine setup doc. Noting only because a reader of
`printproof3d-integration.md` (the "Scope today" / readiness-card discussion at L48–50, L78–84) has no
visual to anchor to. Strictly optional.

**Fix path:** None required. Out of scope to add (audit-only). A future docs pass could embed the
mockup in the README "Smart Mesh readiness" paragraph if a visual is wanted.

---

## What's working (credit where due)

- **Honesty on status is exemplary.** The exact failure mode that burned this project before (a doc
  claiming a stage was "done" pre-gate) is explicitly guarded against — every Stage-7 status line
  carries the "implemented on branch, pending the gate, not yet merged or tagged" qualifier, and the
  CHANGELOG keeps the Stage-7 block under `[Unreleased]` with no tag. This is the single most
  important thing this doc set had to get right, and it did.
- **The "advisory, not blocking" framing is disciplined and accurate.** Both the integration doc
  ("Scope today," L78–84) and the ROADMAP (L200) state PrintProof3D is advisory, the deterministic
  gate stays the slice authority, and folding an engine `fail` into the slice gate is a *named future
  follow-up* — never claimed as a current capability. This matches the code (`pipeline.py` leaves the
  slice gate unchanged; readiness is attached to the report only).
- **`docs/printproof3d-integration.md` is a genuinely good engine doc.** It cleanly separates *what it
  is* (MIT Rust engine, optional, not bundled), *how it's wired* (subprocess, never linked, gated on
  the parsed report not the exit code), *how to enable it* (build → point config → it's picked up),
  *the report contract* (a precise `jsonc` schema that matches `_parse_report`), *scope today*
  (advisory), and *privacy* (local-first, coarse history). The privacy section honestly states the
  history store is coarse (no geometry, no prompt) — which matches `PrintRecord` (`history.py` L27–38).
- **The pipeline-diagram consistency is clean.** README and ARCHITECTURE place "Smart Mesh readiness"
  at the same point in the flow (after harden, before confirm/slice), with consistent language.
- **The "worst of two signals" claim is honest and verifiable.** The docs say the card is "never more
  optimistic than either signal," and the code (`smart_mesh.py` L158–171) implements exactly that via
  a tone `max`. Marketing-grade copy that is actually true.
- **The `~`-no-expansion precision is correct and rare.** Many config docs get `~` handling wrong; this
  one correctly says a relative override resolves against the project root with "no `~` expansion,"
  matching `Path(raw)` in `config.py`.

---

## Cross-role notes for the orchestrator

- **No documentation Blocker/Critical/Major.** Stage-7 doc honesty and accuracy clear the gate from
  the writer's chair.
- DOC-001 (source-comment "prints"/"parts" drift) is a hand-off to the **Principal Engineer** role —
  it's a code-comment fix, outside the doc-edit scope, low priority.
- The two Nits (DOC-003, DOC-004) need no action to pass the gate.
