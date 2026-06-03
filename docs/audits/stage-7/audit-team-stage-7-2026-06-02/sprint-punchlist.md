# Stage 7 — Sprint Punch List

All items were fixed in the remediation pass (the stage gate requires 0/0/0/0/0 before tag). Owner
hint = the role that surfaced it. Status: ✅ = fixed + re-verified.

| ID | Sev | Owner | Item | Fix | Status |
|----|-----|-------|------|-----|--------|
| ENG-701 | Major | Eng | History `record` non-atomic race → lost records | process-wide lock + temp-file `os.replace`; 40-writer regression test | ✅ |
| ENG-702 | Minor | Eng | `record` caught only `OSError` vs "never raises" | broadened to `except Exception` | ✅ |
| ENG-703 | Minor | Eng | Profile/record JSON could emit `NaN`/`Infinity` | `allow_nan=False` on both dumps (degrades) | ✅ |
| ENG-704 | Minor | Eng | History pool semantics undocumented (`created_at` unused) | documented all-time-by-design; `created_at` retained for future recency | ✅ |
| UX-001 | Minor | UI/UX | Readiness verdict duplicated the gate badge ("Ready to print" ×2) | gate badge reframed to "Gate: passed / needs review / failed" | ✅ |
| UX-003 | Minor | UI/UX | British "analysed/analysable" in confidence copy + attribution | US "analyzed/analyzable" | ✅ |
| DOC-001 | Minor | Docs | Source comments said "past prints" (output/docs say "parts") | comments aligned to "parts" | ✅ |
| DOC-002 | Minor | Docs | HANDOFF carried two test counts (664 vs 609) | clarified 609 as the Stage-6-gate count | ✅ |
| QA-001 | Minor | QA | New console strings used em-dash (U+2014, not in cp437) | ASCII `-` in the Stage-7 to_text + comparison strings | ✅ |
| TEST-S7-001 | Minor | Test | Gate-failed-recorded-to-history untested | test added (`gate_status == "fail"`) | ✅ |
| TEST-S7-002 | Minor | Test | `mesh_unanalysable`→Low-over-engine-High untested | precedence test added | ✅ |
| TEST-S7-003 | Minor | Test | `_MIN_SAME_TYPE` exactly-2 boundary untested on `compare_phrase` | boundary test added | ✅ |
| ENG-705 | Nit | Eng | `assess_readiness` sat outside the never-raises guard | wrapped + `_fallback_readiness(gate)` | ✅ |
| ENG-706 | Nit | Eng | Runner discards stderr (undocumented) | documented (report file is the contract; output captured, not inherited) | ✅ |
| ENG-707 | Nit | Eng | `binaries.printproof3d` reads as "configured" but is inert | comment clarified: binary not shipped, path inert until built | ✅ |
| UX-004 | Nit | UI/UX | Green ✓ for not-yet-done recommendations | `→` arrow in the accent (next-step cue) | ✅ |
| UX-005 | Nit | UI/UX | Gauge number crowds the arc mouth at small widths | 32px + `bottom:0` clearance | ✅ |
| DOC-003 | Nit | Docs | (= ENG-707) engine path active-but-inert | same fix as ENG-707 | ✅ |
| DOC-004 | Nit | Docs | Readiness mockup linked only from HANDOFF | referenced from CHANGELOG | ✅ |
| TEST-S7-004 | Nit | Test | Two near-tautological asserts | reviewed — real structural-eq determinism check; no change needed (per the role) | ✅ |
| QA-002 | Nit | QA | Demo can't drive a gate-FAIL card live | by design (safe-envelope sliders); gate-fail covered by tests | ✅ |
