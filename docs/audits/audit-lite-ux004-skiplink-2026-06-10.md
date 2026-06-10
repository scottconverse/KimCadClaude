# Audit Lite — UX-004 skip link + verification fixes (commit 1493dde)
**Date:** 2026-06-10
**Scope:** Commit `1493dde` on `beta-readiness-audit-remediation`: skip-to-content link + `main#kimcad-main` landmark on all four routes, two new tests, `.gitignore` scratch additions + hygiene-test extension, duplicate win32 guard merge in `find_cadquery_interpreter`, Codex walkthrough evidence committed.
**Reviewer:** Claude (audit-lite) — adversarial self-review; checks chosen to attack the change, not confirm it.

## TL;DR
Ship. The four named risks were each checked concretely and none materialized: no element-selector CSS coupling, no duplicate-landmark path, no ARIA conflicts, and the committed SPA assets are byte-identical to a fresh rebuild. Tests cover the new behavior on both the App and Workspace sides.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

## Findings
None.

## Adversarial checks performed (evidence)
- **`div`→`main` CSS regression:** `kc-workspace-wrap` is styled only via the class selector (`styles.css:491`); grep over `frontend/src` finds no `div.kc-*` / element-qualified selector that the tag change could break.
- **Duplicate `main#kimcad-main`:** `App.tsx`'s final return is a strict ternary chain (MyDesigns | Settings | Landing | Workspace) — exactly one route mounts per render, so exactly one landmark. Verified all five `<main>` declarations (4 routes + none elsewhere) via grep.
- **ARIA/role conflicts:** `nav` (VersionRail) and `aside` (ChatPanel/RightPanel) nested inside `main` is valid HTML/ARIA; the skip link precedes the focus-trapped modals, which own focus while open (correct — a modal route shouldn't expose skip-to-content).
- **Asset/source drift:** fresh `npm run build` after the commit → zero diff against the committed `src/kimcad/web/assets/` (byte-identical, the repo's reproducibility bar).
- **Runtime:** verified live in the served demo before commit — link is the shell's first focusable, hidden offscreen until `:focus-visible` (programmatic `.focus()` correctly does *not* reveal it), `href="#kimcad-main"` resolves on the landing route.
- **Tests:** vitest 289 passed (2 new: App skip-link first-focusable+target, Workspace landmark); typecheck clean; `ruff` clean; hygiene+cadquery suites 45 passed.

## What's working
- The landmark id lives on each route's own `<main>` rather than a wrapper, so the skip target is always the active route's content — simpler than a shared wrapper and immune to route-specific layout CSS.
- The hygiene test now pins all four scratch-artifact patterns, so the next stray log/probe-install class gets caught by CI, not by an auditor.

## Watch items
- During the Workspace lazy-chunk load (`Suspense` fallback), the skip-link target is briefly absent — a click in that ~100 ms window no-ops. Transient and harmless; fold a `id="kimcad-main"` onto the fallback div if it ever shows up in a walkthrough.

## Escalation recommendation
No escalation needed — scoped accessibility/hygiene slice, zero findings.
