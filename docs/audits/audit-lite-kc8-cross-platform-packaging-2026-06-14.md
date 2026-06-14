# Audit Lite — #13 (KC-8) cross-platform packaging
**Date:** 2026-06-14
**Scope:** The cross-platform packaging decision + the from-source readiness fixes: `docs/dev/cross-platform-packaging.md` (new decision doc), `src/kimcad/paths.py` (per-OS data dir), `scripts/fetch_tools.py` (actionable off-Windows messages), `config/default.yaml` (mac/Linux guidance), `tests/test_paths.py` + `tests/test_fetch_tools.py` (new tests), and the doc reconciliation (README, install-guide, CHANGELOG).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship. The issue's deliverable is "the cross-platform packaging path is scoped with a decision" — that decision is written, grounded in a 4-agent investigation, and paired with the readiness fixes that make the from-source mac/Linux path genuinely first-class. Windows behavior is byte-identical (verified). One Minor (an overclaim of the verification level) was found and **fixed in this pass**.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

(One Minor surfaced and was remediated in-pass — see Finding 001. Final state is 0/0/0/0/0.)

## Findings

### FINDING-001 Minor (RESOLVED in this pass): "runs from source today" overstated the verification level
**Dimension:** Docs
**Evidence:** The decision doc (§1, TL;DR), README Platform notes, and the CHANGELOG entry asserted KimCad "runs on macOS/Linux from source today." The evidence is **static analysis** (the readiness audit: all platform-specific imports guarded; the `kimcad web` path is pure stdlib) plus the cross-platform test design — **not** a real run on macOS/Linux hardware (the dev box is Windows).
**Why it matters:** The project's standing honesty rule keeps "validated against a mock / by analysis" distinct from "validated on hardware." An unqualified "runs today" reads as empirical runtime proof that wasn't obtained.
**Fix path (done):** Added an explicit "code-substantiated, not yet exercised on real mac/Linux hardware" caveat to the decision doc (§1 honesty note + a TL;DR footnote), the README Platform notes, the CHANGELOG entry, and the install-guide pointer — mirroring the connectors' "validated, not yet metal-validated" posture.

## What's working
- **Honest scope.** The decision (defer installer *artifacts*; ship from-source support now) is the in-scope deliverable the issue explicitly allows, and the reason is a real external gate (Apple Developer cert) + a stage-verify constraint (the gate is intrinsically Windows-only and can't validate a mac/Linux artifact on this box), not a speed shortcut.
- **Windows behavior preserved.** `paths.py` refactors the data-dir resolution into `_per_user_data_root()` with a `win32` branch byte-identical to before (`%LOCALAPPDATA%\KimCad`); verified at runtime (`C:\Users\…\AppData\Local\KimCad` + `\webview`) and by the unchanged `test_paths`/`test_design_store` suites (40+20 pass).
- **Real readiness fixes, not just docs.** The `~/AppData/Local` Windows-shaped fallback is now per-OS (`~/Library/Application Support` / `$XDG_DATA_HOME` / `~/.local/share`); `fetch_tools` off-Windows failures are now actionable (official download + `config/local.yaml` + the browser fallback) instead of a bare `SystemExit`; `default.yaml` carries a mac/Linux example block.
- **Tested cross-platform on a Windows box.** The new mac/Linux `paths` branches are exercised by monkeypatching `sys.platform`; the `fetch_tools` hints by simulating `_platform_key` — so the off-Windows behavior is covered without a non-Windows runner. 14 targeted tests pass; ruff clean.
- **Scope discipline.** The audit's suggested `binary_path()` `shutil.which()` fallback was deliberately **not** taken — it would break `orca_profiles_root()` for a system OrcaSlicer (profiles live inside the app bundle, not beside `/usr/bin/orca-slicer`). The lower-risk `default.yaml` guidance achieves the same user goal. Noted in the decision doc.
- **Grounded recipes.** The per-OS recipes (briefcase `.app`/`.dmg`; AppImage browser-fallback) name concrete tools, the WKWebView/WebKit2GTK backends, the signing/notarization gates, the stage-verify path on free hosted runners, and per-OS effort — a dev could start the lane from the doc.

## Watch items
- **The from-source path needs hardware proof.** The code-verified claim becomes empirical only when the first hosted-runner lane (the Linux browser-fallback AppImage, per §6) runs `kimcad web --demo` green on real Linux. Until then the caveat stands.
- **`README` badge.** The `platform-Windows` badge reflects the shipped *installer* (correct), but a reader scanning only the badge won't see the from-source nuance. Left as-is deliberately to avoid implying mac/Linux installers exist; the Platform notes carry the truth.

## Escalation recommendation
No escalation needed. CI-only + doc + a contained, well-tested paths refactor; Windows behavior unchanged; the decision is honest and complete.
