# Slice 7 — Sprint punch list

Every item from the 5-role audit, with the role that surfaced it. **All 18 closed → 0/0/0/0/0.**
Resolution detail in `REMEDIATION.md`; re-verified ruff clean, 740 backend + 162 frontend tests pass, build clean.

| # | ID | Sev | Owner role | Item | Status |
|---|----|-----|-----------|------|--------|
| 1 | DOC-001 | Major | Docs | CHANGELOG `[Unreleased]` frozen at Slice 1; add Slices 2–7 | ✅ Closed |
| 2 | DOC-002 | Major | Docs | README banner/section only mention Slice 1; on-ramp undocumented | ✅ Closed |
| 3 | TEST-701 | Major | Test | `/api/photo-seed` 400 "Empty upload" branch untested | ✅ Closed |
| 4 | TEST-702 | Major | Test | `uploadPhoto` server-error (413/422) mapping untested | ✅ Closed |
| 5 | ENG-002 | Minor | Eng | Empty vision on a stale Ollama looks like a bad photo | ✅ Closed (stderr breadcrumb) |
| 6 | ENG-003 | Minor | Eng | `get_config()` outside the never-500 try | ✅ Closed |
| 7 | ENG-001 | Minor | Eng | Function-local stdlib imports in `describe_photo` | ✅ Closed (moved to top; webapp late import kept) |
| 8 | UX-001 | Minor | UI/UX | Error copy promises "describe in words"; card offers only re-pick | ✅ Closed (copy: "cancel and describe…") |
| 9 | UX-002 | Minor | UI/UX | Confirm card group label duplicates the affordance label | ✅ Closed (phase-specific aria-label) |
| 10 | DOC-003 | Minor | Docs | HANDOFF resume block one slice stale | ✅ Closed |
| 11 | DOC-004 | Minor | Docs | usability-plan Slice 6/7 headers lack status markers | ✅ Closed |
| 12 | DOC-005 | Minor | Docs | ARCHITECTURE "Two jobs"; `/api/photo-seed`+settings absent | ✅ Closed |
| 13 | TEST-703 | Minor | Test | drag-drop `onDrop` path untested | ✅ Closed |
| 14 | TEST-704 | Minor | Test | "Use a different photo" re-pick + object-URL revoke untested | ✅ Closed |
| 15 | ENG-004 | Nit | Eng | Non-ASCII curly punctuation in copy | ✅ Closed (consistent house style — no change) |
| 16 | UX-003 | Nit | UI/UX | "Use a different photo" vs "Try another photo" | ✅ Closed (unified) |
| 17 | DOC-006 | Nit | Docs | prompt "millimetres" (British) | ✅ Closed (→ "millimeters") |
| 18 | TEST-705 | Nit | Test | FakeProvider-vs-real-router split (note) | ✅ Closed (correct as-is — no change) |
