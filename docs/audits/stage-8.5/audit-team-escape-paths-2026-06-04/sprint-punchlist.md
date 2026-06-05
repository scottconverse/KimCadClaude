# Escape-paths stage — Sprint punch list

All 16 findings, with the role that surfaced each. **All closed → 0/0/0/0/0** (detail in `REMEDIATION.md`). Re-verified: build clean, 175 frontend tests pass.

| # | ID | Sev | Role | Item | Status |
|---|----|-----|------|------|--------|
| 1 | ENG-001 | Major | Eng | Reopen shows "Designing…" overlay w/ garbage timer + dead Cancel | ✅ Closed (restoring overlay) |
| 2 | TEST-801 | Major | Test | Cancel tests don't assert "no error shown" | ✅ Closed |
| 3 | DOC-ESC-001 | Major | Docs | Escape hardening undocumented in CHANGELOG | ✅ Closed |
| 4 | ENG-002 | Minor | Eng | Reopen overlay's Cancel/Esc are dead no-ops | ✅ Closed (same fix) |
| 5 | ENG-003 | Minor | Eng | slice/import don't abort the prior in-flight req | ✅ Closed |
| 6 | UX-801 | Minor | UI/UX | Ticking timer chants in a screen reader | ✅ Closed (aria-hidden) |
| 7 | UX-802 | Minor | UI/UX | 80% busy wash weakens contrast over a framed part | ✅ Closed (94%) |
| 8 | TEST-802 | Minor | Test | isAbortError DOMException branch untested | ✅ Closed |
| 9 | TEST-803 | Minor | Test | refine-cancel branch untested | ✅ Closed |
| 10 | TEST-804 | Minor | Test | real Viewport Cancel/timer never rendered in tests | ✅ Closed (Viewport.test) |
| 11 | DOC-ESC-002 | Minor | Docs | HANDOFF resume block stale on the escape stage | ✅ Closed |
| 12 | DOC-ESC-003 | Minor | Docs | usability plan doesn't note the insertion/Slice 9 overlap | ✅ Closed |
| 13 | ENG-004 | Nit | Eng | PhotoOnramp double-revoke | ✅ Closed (harmless, no change) |
| 14 | UX-803 | Nit | UI/UX | three "computer's AI" phrasings differ | ✅ Closed (context-correct, no change) |
| 15 | TEST-805 | Nit | Test | postSlice lacks the signal-forwarding assertion | ✅ Closed |
| 16 | QA-nit | Nit | QA | theoretical post-unmount act warning | ✅ Closed (React-18 no-op) |
