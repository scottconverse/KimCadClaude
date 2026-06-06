# Documentation Deep-Dive — Stage 0–3 Backend Backfill

**Role:** Senior Technical Writer (independent, skeptical)
**Scope:** Docs accuracy for the shipped backend foundation — deterministic pipeline (Stage 0/5-era spine), gated export (Stage 1), send-to-printer connectors + MCP (Stage 2), printer coverage + connector honesty (Stage 3). Backfill of an owed audit against the **current** code on branch `stage-0-7-audit-backfill` (HEAD `a83024d`).
**Mode:** AUDIT-ONLY. Gaps are recorded as findings; needed drafts are noted, not written.
**Date:** 2026-06-06

Docs reviewed: `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, `config/default.yaml` comments.
Code cross-checked: `pipeline.py`, `slicer.py`, `printability.py`, `connectors.py`, `printer_connector.py`, `config.py`, `cli.py`, `webapp.py` (status/slice/send paths), `mcp_server.py`, `mock_printer.py`, `tests/test_slicer.py`.

---

## Verdict

The backend docs are **unusually honest and accurate** for a project at this stage. The load-bearing "no real hardware has been driven yet" disclaimer is present and repeated everywhere send/printer is discussed; the gate-is-the-slice-authority boundary is stated *and* enforced in code (CLI, web `/api/slice`, web `/api/send`, MCP); the connector-reason vocabulary in the README matches the code's typed `reason` values exactly; and the "all three printers proven end to end" claim is backed by a real parametrized live-slice test. No Blockers, no Critical doc lies. The findings are drift between documents that have diverged over eight stages — chiefly a stale ROADMAP "Current baseline" section and a couple of mismatched figures — none of which mislead a user about what the backend *does* or *doesn't* do.

---

## Severity counts

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 4 |
| Nit | 3 |
| **Total** | **9** |

---

## What's working (credit where due)

- **The honesty disclaimer is load-bearing and everywhere it should be.** `README.md:13–14` ("software/profile validation, not yet a real print"), `README.md:201–203` ("**No real hardware is driven yet** … *software-complete and mock-tested*, not hardware-verified"), `ROADMAP.md:65–66` ("**No part has driven real hardware yet**"), `printer_connector.py:20–22`, `connectors.py:1` heading, and `config/default.yaml:160–161` all say the same true thing in the same honest register. This is exactly the discipline the audit brief flagged as load-bearing, and it holds. [stage 2][stage 3]
- **Gate-is-authority is documented AND enforced.** `README.md:49`, `ARCHITECTURE.md:32–33`, `printability.py:1–11` all call the deterministic gate the slice authority and PrintProof3D advisory; the code backs it — `pipeline.py:525–539` returns `gate_failed` without slicing, `webapp.py:1736–1740` refuses a gate-failed part on `/api/slice` server-side, and `cli.py:282–290` refuses to `--send` one. Words match behavior.
- **The connector-reason table is exact.** `README.md:245–253` matches the `reason` vocabulary in `printer_connector.py:53–66`; the subtle claims ("`auth` appears on send; status shows `error` + `detail`" and "`busy` on send is PrusaLink-409-only") are verified true in `webapp.py:1246–1251` and the connector classes.
- **The "all three printers, end-to-end" claim is test-backed**, not marketing — `tests/test_slicer.py:553–554` parametrizes a live OrcaSlicer slice across `bambu_p2s`, `bambu_a1`, `elegoo_neptune_4_max`. `README.md:155–158` and `CHANGELOG.md:345–350` are honest.
- **ARCHITECTURE.md is excellent.** The pipeline ASCII diagram (`ARCHITECTURE.md:19–37`) matches `pipeline.py`'s actual stage order (gate → orient → harden → readiness → confirm/slice), and the per-module map (`ARCHITECTURE.md:73–104`) is accurate to each leaf module's real responsibility. The Stage-1 "Gated export, wired" note (`ARCHITECTURE.md:61–69`) and the slicer/connector entries are correct against `slicer.py` and `printer_connector.py`.
- **`config/default.yaml` comments are accurate and load-bearing.** The "no cross-vendor generic fallback" / "Elegoo ships no TPU" comments (`default.yaml:88–90, 126–133`) match `slicer.py:413–420` (raises `OrcaProfileError`, no fallback) and `tests/test_slicer.py:265–291`. The Gate-vs-slice temperature CONTRACT note (`default.yaml:138–145`) is a genuinely good, honest clarification.

---

## Findings

### DOC-001 — Major — Accuracy — ROADMAP "Current baseline" header says "as of Stage 4" but describes everything through Stage 8.5 as done, with stale test counts [stage 0]

**Evidence:** `ROADMAP.md:35` — heading "## Current baseline (honest, as of Stage 4 — DONE, merged, tagged)". The same paragraph (`ROADMAP.md:35–66`) then narrates Stages 5, 6, 7, and 8.5 as all DONE/tagged, and cites "**404 tests passing** … vitest, 19 passed" (`ROADMAP.md:39–40`). The CHANGELOG's current figure is "763 pytest (non-live) + 4 live OrcaSlicer + 262 vitest" (`CHANGELOG.md:36–37`); `HANDOFF.md:355` still echoes the old "19 passed" too.

**Why this matters:** The "Current baseline" section is the single orientation anchor a new engineer reads to learn where the project stands. Its header ("as of Stage 4") flatly contradicts its own body (through 8.5), and the cited test counts are ~360 pytest and ~240 vitest stale. A new team member trusts this section to know what's verified; an internally self-contradicting baseline erodes trust in the rest of the doc. Behavioral-claim drift (the verification numbers a reader would quote) → Major per the framework.

**Blast radius:**
- Adjacent docs: `HANDOFF.md:355` repeats "vitest, 19 passed"; any future "as of Stage N" baseline edits should update both.
- Migration: none.
- Fix path: rename the header to "Current baseline (honest, as of Stage 8.5 — DONE)"; replace the test counts with the CHANGELOG's current figures or, better, drop the hard numbers from the prose baseline and point to the CHANGELOG/audit dir as the single source of truth so it can't go stale again.

### DOC-002 — Major — Accuracy — CLI `--send` help advertises `moonraker`/`prusalink` as ready targets, but they ship commented-out [stage 3]

**Evidence:** `cli.py:81–82` help text: "send the print job to a configured connector by name (e.g. 'mock', 'octoprint', 'moonraker', 'prusalink')." But in `config/default.yaml` only `mock` and `octoprint` are active; `moonraker` (`default.yaml:172–175`) and `prusalink` (`default.yaml:178–182`) are commented examples. A user who runs `kimcad design "..." --send moonraker` on a stock config hits `cli.py:245–248` "Unknown connector 'moonraker'. Configured connectors: mock, octoprint".

**Why this matters:** The CLI's own `--help` is documentation, and here it lists two targets that don't resolve out of the box. The README handles this correctly — `README.md:219–222` explains moonraker/prusalink must be uncommented first — but the CLI help string gives the returning user (who reads `--help`, not the README) four equal-looking options, two of which fail. Behavioral mismatch between documented affordance and shipped config → Major.

**Blast radius:**
- Adjacent code/docs: keep aligned with `default.yaml`'s active connectors and `README.md:204–211` (the supported-connections table, which correctly shows all four as *configurable*).
- Migration: none.
- Fix path: soften the CLI help to "(e.g. 'mock', 'octoprint'; add 'moonraker'/'prusalink' under `connectors:` first — see the README)", or list only the shipped-active connectors. Pure copy edit in `cli.py:81–82`.

### DOC-003 — Minor — Accuracy — CHANGELOG Stage 1 still states a "`Generic <MATERIAL>` filament fallback" that Stage 3 removed [stage 1]

**Evidence:** `CHANGELOG.md:150–153` (Stage 1 entry): "a configured printer + material maps to the three on-disk profile JSONs … with a `Generic <MATERIAL>` filament fallback." `CHANGELOG.md:222–224` (Stage 3 entry) then says the cross-vendor "`Generic <MATERIAL>` fallback was **removed**." The current code (`slicer.py:413–420`) has no fallback — an unmapped material raises `OrcaProfileError`.

**Why this matters:** This is technically *correct* as an append-only Keep-a-Changelog history (Stage 1 added it, Stage 3 removed it). The risk is a reader scanning the Stage 1 section in isolation concludes the shipped behavior is "falls back to a generic profile," which is the exact mis-slice-on-wrong-machine behavior the project deliberately removed. Low exposure (the Stage 3 entry corrects it 70 lines down) → Minor.

**Fix path:** Add a one-line forward-reference at `CHANGELOG.md:153` — "(superseded in Stage 3: the generic fallback was removed; an unmapped material is now honestly 'not available')." Preserves changelog history while preventing a stale read.

### DOC-004 — Minor — Completeness — README "Send to a printer" omits Bambu (P2S/A1) from the supported-connections table without naming the gap [stage 3]

**Evidence:** `README.md:204–211` lists `loopback`, `octoprint`, `moonraker`, `prusalink`. Kim's primary printers are two Bambu machines (P2S + A1), which have no native connector — that's deferred to Stage 10 (`ROADMAP.md:120–121, 266–268`). The README's send section never tells the reader that *the two flagship printers* can't be sent to natively yet (OctoPrint is the only path, and only if the user runs OctoPrint in front of the Bambu).

**Why this matters:** A reader sees "all three printers are fully sliceable and proven" (`README.md:155–158`) in one section and a connection table in the next, and could reasonably infer they can *send* to the P2S directly. They can slice for it; they can't natively send to it. The ROADMAP is honest about this; the README's user-facing send section isn't. First-time-user clarity gap → Minor (not Major, because no false capability is *claimed* — it's an omission, and sending from the browser is itself deferred).

**Fix path:** Add one line under the connections table: "Bambu (P2S/A1) have no native connector yet — drive them via OctoPrint, or wait for the Stage 10 Bambu-native path. The slice/download path works for all three today."

### DOC-005 — Minor — Accuracy — README implies the OctoPrint mock is the only runnable mock in the numbered walkthrough; Moonraker/PrusaLink mocks are mentioned only in passing [stage 2][stage 3]

**Evidence:** `README.md:258–265` gives a clean numbered "try OctoPrint with no hardware" walkthrough. The Moonraker and PrusaLink mock servers (`python -m kimcad.mock_moonraker`, `python -m kimcad.mock_prusalink`) are named once at `README.md:230–232` but have no equivalent walkthrough, even though they exist and are tested (`ARCHITECTURE.md:90, 92`; mock modules present).

**Why this matters:** A returning user who wants to exercise the Klipper or Prusa path has the building blocks but no recipe; they must reverse-engineer the port and env-var from the config comments. Completeness gap on a real, shipped path → Minor.

**Fix path:** Add two short parallel walkthroughs, or a single note: "The Moonraker and PrusaLink connectors have the same shape — start their mock (`python -m kimcad.mock_moonraker` / `mock_prusalink`), point a `connectors:` entry at it, set the env var if any, and `--send <name>`."

### DOC-006 — Minor — Accuracy — `default.yaml` build-volume VERIFY comments are honest but the README's "fully sliceable / proven" framing doesn't carry the same caveat [stage 1][stage 3]

**Evidence:** `config/default.yaml:94` and `:107–109` carry "VERIFY exact P2S envelope (P-series standard assumed)" / "VERIFY exact A1 envelope" markers — the build volumes are *assumed*, not confirmed against the real machines. The README/CHANGELOG "fully sliceable and proven end to end" language (`README.md:155–158`, `CHANGELOG.md:345–346`) is true for *slicing* (the slice succeeds against the bundled profile) but the build-volume numbers the Printability Gate enforces are unverified assumptions.

**Why this matters:** "Proven end to end" is accurate for the slice pipeline; it could be over-read as "the printer envelope is confirmed correct." The gap is small (the slice uses the OrcaSlicer machine profile's own plate, not the config number; the config build_volume only feeds the *gate's* fit check), and the config is honest internally — but the user-facing "proven" word doesn't inherit the VERIFY caveat. Low exposure → Minor.

**Fix path:** One clause in the README requirements/printer note: "build-volume numbers for the Bambu machines are nominal/assumed pending on-metal verification (the slice itself uses OrcaSlicer's own machine profile)."

### DOC-007 — Nit — Tone/Consistency — "Phase 1" vs "Stage N" numbering coexist without a one-line reconciliation [stage 0]

**Evidence:** `printability.py:1, 7` and `pipeline.py` docstrings, `bench/` and `cli.py:1` speak of "Phase 1 / Phase 2"; the ROADMAP and tags use "Stage 0–11" (`ROADMAP.md:8–10` does explain the tag numbering, but doesn't map "Phase 1" → which stages). A new reader meets both vocabularies.

**Fix path:** Add one line to `ROADMAP.md:8–10`'s numbering note: "Code docstrings' 'Phase 1' ≈ Stages 0–1 (the deterministic print loop); 'Phase 2' ≈ the web UI (Stage 4+)."

### DOC-008 — Nit — Accuracy — `cli.py` module docstring says "Five subcommands" and lists the right five, but the prose header says "the Phase-1 user surface" while three of the five are Stage 6/2+ [stage 0]

**Evidence:** `cli.py:1` "the Phase-1 user surface (spec §5)"; the listed subcommands include `models` and `bakeoff` (Stage 6) and `--send` (Stage 2/3). Minor staleness in a docstring header.

**Fix path:** "the user-facing CLI surface" instead of "the Phase-1 user surface."

### DOC-009 — Nit — Completeness — README LLM "model_name" verify warning is strong for cloud but the local default's verify status isn't mentioned [stage 0]

**Evidence:** `README.md:124` rightly warns "Verify the cloud `model_name` against your provider's current model list." The local default `gemma4:e4b` is settled and correct per project memory; no doc issue with the model itself. Nit only: the README never says *why* it's safe to trust the local default while the cloud ones are examples — a half-sentence ("the local default is pinned and tested; the cloud tags are examples") would close the asymmetry.

**Fix path:** Optional half-sentence at `README.md:124`. Cosmetic.

---

## Cross-role blast-radius note

DOC-001 (stale baseline) and DOC-002 (CLI help drift) share a root cause: **figures and affordance lists hand-maintained in prose drift as stages land.** The durable fix is to make the CHANGELOG / audit-dir the single source of truth for test counts and stage status, and have ROADMAP/HANDOFF/CLI-help reference rather than restate them. Group DOC-001 + DOC-002 + DOC-003 + DOC-008 as one "de-stale the hand-maintained claims" pass.

No findings touch the gate-authority boundary, the no-hardware honesty disclaimer, or the connector-reason contract — those three load-bearing claims are accurate and code-backed.
