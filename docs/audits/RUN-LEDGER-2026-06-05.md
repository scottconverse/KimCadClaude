# KimCad — Finish-the-product run ledger (started 2026-06-05)

**Mandate (Scott, 2026-06-05):** do the per-stage audits that were owed AND finish the build to a
releasable beta. Don't stop except on a catastrophic break. Every audit is the REAL skill via
independent agents, every finding fixed (Blocker→Nit), evidence committed to VC. This ledger is the
resume anchor — keep it current so the run survives compaction.

**Branch:** `stage-8.5-usability` (forward build continues here per stage; merges to `main` at each
stage gate). **Resume rule:** read this file + `HANDOFF.md`, find the first row not ✅, continue there.

## Program (execution order)

| # | Phase | wiring-audit | audit-team 0/0/0/0/0 | merge+tag | status |
|---|---|---|---|---|---|
| 1 | Stage 8.5 Slice 11 (responsive/a11y/copy/polish) — build + audit-lite | n/a (slice) | ✅ audit-lite 0/0/0/0/0 (`95b25e0`) | n/a | ✅ DONE |
| 2 | Stage 8.5 STAGE GATE (whole stage) | ✅ wiring-audit PASS 0/0/0/0 | ⏳ audit-team ran (0B/0C/11Maj/22Min/11Nit=44); REMEDIATING to 0/0/0/0/0 | ☐ tag `stage-8.5` | ⏳ IN PROGRESS |
| 3 | Backfill Stage 4 (SPA) audits | ☐ | ☐ (refresh) | n/a (already on main) | ☐ |
| 4 | Backfill Stage 5 (templates/sliders) audits | ☐ | ☐ (refresh) | n/a | ☐ |
| 5 | Backfill Stage 6 (model layer) audits | ☐ | ☐ (refresh) | n/a | ☐ |
| 6 | Backfill Stage 7 (Smart Mesh) audits | ☐ | ☐ (refresh) | n/a | ☐ |
| 7 | Backfill Stage 0–3 audit-team into VC | n/a (backend) | ☐ | n/a | ☐ |
| 8 | Stage 8 (CadQuery backend) — build + gate | ☐ | ☐ | ☐ tag `stage-8` | ☐ |
| 9 | Stage 9 (image on-ramp) — build + gate | ☐ | ☐ | ☐ tag `stage-9` | ☐ |
| 10 | Stage 10 (direct-print + layer preview) — build + gate | ☐ | ☐ | ☐ tag `stage-10` | ☐ |
| 11 | Stage 11 (installer + beta) — build + gate | ☐ | ☐ | ☐ tag `stage-11` | ☐ |

## Audit gap baseline (verified 2026-06-05, why this run exists)
- **wiring-audit** had run on only 2 Stage-8.5 slices (1, 2–4). NEVER on shipped stages 0–7.
- **audit-team** committed in-repo for stages 4,5,6,7 only; 0–3 audited outside VC (unproven) or not committed.
- Stage 8.5 per-slice gate was incomplete: slices 8 & 9 had no committed audit artifact; 8,9,10 had no audit-team/wiring-audit.

## Stage 8.5 stage-gate remediation tracker (fix all 44 → re-audit → 0/0/0/0/0 → merge → tag)
- ✅ **Docs (9)** — DOC-001..006 + DOC-N1/N2/N3 — commit `d2764ad`.
- ✅ **Engineering (7)** — ENG-001..007 (incl. geometry-version stamp + reopen re-gate + tests) — commit `c1261f2`.
- ◐ **UI/UX (20)** — IN PROGRESS. **Sub-batch A done:** UX-001/009 (right-column hierarchy CSS), UX-005 ("?" Help button), UX-007 (landing badge), UX-012 (format-purpose note), UX-013 (dedup save link), UX-015 (disabled-slice reason), UX-017 (lighter rec arrow). **Remaining (sub-batch B):** UX-002 (printability icon-tile checks — needs finding label/detail), UX-003+010 (refine chips), UX-004 (mobile sticky CTA), UX-006 (printer-status chip), UX-008 (dup "Designing…" row), UX-011 (v1 version cue), UX-014 (apostrophe consistency), UX-016/018 (confirm-intentional nits — document, no code change).
- ☐ **Tests (5)** — TEST-001..005.
- ☐ **QA (3)** — QA-001..003.
- ☐ Re-audit (audit-team + re-check wiring) → 0/0/0/0/0 → merge `main` → tag `stage-8.5`.

## Log
- 2026-06-05: Run started. Slices 1–10 of Stage 8.5 built + pushed (Slice 10 = `7fc5415`). Slice 11 built + gated + pushed (`95b25e0`). Stage-8.5 stage gate ran: wiring-audit PASS; audit-team 44 findings. Remediation: docs (`d2764ad`) + engineering (`c1261f2`) done; UX/test/QA next.
