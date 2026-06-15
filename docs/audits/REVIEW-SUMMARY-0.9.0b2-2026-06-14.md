# KimCad 0.9.0b2 — Second-Pass Review Summary (all three audits)

**Date:** 2026-06-14 · **Build:** 0.9.0b2 (`f92c2b1`, tag `v0.9.0b2`)
**Passes:** (1) cleanup/version+docs review · (2) real-mode `/walkthrough` · (3) 5-role `/audit-team` (whole repo)
**Status of fixes:** **HELD** — nothing remediated, committed, or pushed. No product files were modified during any pass (`git diff` clean; only new `docs/audits/` reports). This is the plan; awaiting your go-ahead.

---

## The one-paragraph picture

KimCad 0.9.0b2 is **engineered and hardened well above a 0.9-beta bar** — the server shrugged off ~30 adversarial inputs with zero 500s/leaked tracebacks, the connector mocks are adversarial, the design system is AA-contrast/focus-guarded, and the real happy path (describe → AI design → printability gate 92/100 → live sliders → slice → download → send, incl. the new Duet/Marlin in the picker) works end-to-end and looks great. Three things keep it from a clean bill: **(A)** the **default local model can't reliably build the product's own example prompts** — it fails 2–3 of the 3 landing chips after 100–160 s and sometimes emits non-code as OpenSCAD source, and the demo-only CI is blind to it; **(B)** the **doc front door is a release behind**, including one **Blocker** — the install guide's SHA-256 verify command names an installer the b2 release doesn't publish, so the only integrity check on an unsigned binary fails; **(C)** **ARCHITECTURE.md documents a removed untrusted-codegen path as live**. None is a wiring defect. The fixes are mostly fast and doc-level, except the model issue, which needs your direction.

---

## Unified severity picture (deduped)

| Sev | Count (unique) | The items |
|---|---|---|
| **Blocker** | 1 | Install-guide checksum command names the wrong installer (DOC-001) |
| **Critical** | 4 | Default model fails the landing's own prompts (UX-001/TEST-001/QA-001/ENG-002) · codegen emits non-code → render-fail (QA-002) · ARCHITECTURE describes removed fallback as live (DOC-002/ENG-003) · ARCHITECTURE omits Duet-Marlin/session-token/macOS-Linux (DOC-003) |
| **Major** | ~9 | failure-loop refine chips (UX-002) · README-not-scanned-by-version-test (TEST-002) · bambu deps ship to everyone (ENG-001) · sync `/api/design` thread (ENG-004) · manual omits b2 features (DOC-004) · no landing page (DOC-005) · 3D viewport keyboard-inaccessible (UX-003) · "about 90" vs 86 families · version drift across README/manual/Discussion |
| Minor / Nit | ~many | see deep-dives (footprint, scheme-allowlist, glossary, WebGL warnings, …) |

The single highest-leverage area is **(A)** — it's the default config, the featured path, and Kim's most likely first action. Note it's **hit-or-miss, not always-fail**: the walkthrough got a clean coaster in ~40 s while the QA pass got 3/3 failures in its window.

---

## Your decisions (captured)

1. **Landing page** → ✅ approved to **build + publish** (honest, marketing-oriented; non-technical + technical + architecture sections; links to installer / user manuals / repo; GitHub Pages). Queued for remediation.
2. **Docs** → README + a **professionally formatted, complete user manual** (non-technical / technical / architecture) are **required**; format-flexible (need not be PDF) but polished and complete.
3. **Remediation** → **held** until you say go. When you do, the order is in [`sprint-punchlist.md`](audit-team-0.9.0b2-2026-06-14/sprint-punchlist.md): DOC-001 first (the Blocker), then the default-model cluster (needs your approach choice), then the ARCHITECTURE pass, then the landing page + manual rebuild.
4. **Open decision for you:** the **default-model approach** (curate chips + broaden template matching [cheapest] / stronger default model / cloud-default / validate generated `.scad` before render) — engineering can't pick this alone. Detail in the executive audit's "Cross-role findings → A".

> **Heads-up:** a `/audit-team` subagent left a **suggestion chip** to "fix the stale README + add the version-test guard." If you click it, it will start a remediation session — which conflicts with the current hold. Ignore/dismiss it unless you want that fix to start now.

---

## All produced reports — drive paths + clickable links

### Pass 1 — Cleanup review (version consistency + docs currency)
- **Drive:** `C:\Users\scott\Desktop\Code\kimcadclaude\docs\audits\cleanup-review-0.9.0b2-2026-06-14.md`
- **Open:** [cleanup-review-0.9.0b2-2026-06-14.md](cleanup-review-0.9.0b2-2026-06-14.md)

### Pass 2 — Real-mode walkthrough (live UI audit, 35 screenshots)
- **Drive (report):** `C:\Users\scott\Desktop\Code\kimcadclaude\docs\audits\walkthrough-0.9.0b2-2026-06-14\AUDIT_walkthrough.md`
- **Open:** [AUDIT_walkthrough.md](walkthrough-0.9.0b2-2026-06-14/AUDIT_walkthrough.md)
- **Drive (evidence):** `C:\Users\scott\Desktop\Code\kimcadclaude\docs\audits\walkthrough-0.9.0b2-2026-06-14\screens\` (35 PNGs — e.g. `20-real-workspace.png`, `26-real-send.png`, `41-sketch-seed.png`, `09-workspace.png`)

### Pass 3 — Audit-team (5 roles, whole repo)
- **Drive (folder):** `C:\Users\scott\Desktop\Code\kimcadclaude\docs\audits\audit-team-0.9.0b2-2026-06-14\`
- **Read first →** [00-executive-audit.md](audit-team-0.9.0b2-2026-06-14/00-executive-audit.md)
- [sprint-punchlist.md](audit-team-0.9.0b2-2026-06-14/sprint-punchlist.md) · [next-sprint-watchlist.md](audit-team-0.9.0b2-2026-06-14/next-sprint-watchlist.md)
- Deep-dives: [01 Engineering](audit-team-0.9.0b2-2026-06-14/01-engineering-deepdive.md) · [02 UI/UX](audit-team-0.9.0b2-2026-06-14/02-uiux-deepdive.md) · [03 Documentation](audit-team-0.9.0b2-2026-06-14/03-documentation-deepdive.md) · [04 Test](audit-team-0.9.0b2-2026-06-14/04-test-deepdive.md) · [05 QA](audit-team-0.9.0b2-2026-06-14/05-qa-deepdive.md)

---

*All three passes were audit-only. The 0.9.0b2 release itself remains live and correct; these reviews concern product polish (the default model), the doc front door, and architecture-doc accuracy — not the binary's integrity.*
