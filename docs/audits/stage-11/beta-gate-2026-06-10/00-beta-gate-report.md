# The beta gate — Stage 11 / `0.9.0b1` (2026-06-10)

**Scope:** the Stage 11 diff (`07fb3ad..HEAD`) AND the installed artifact
(`KimCad-Setup-0.9.0b1.exe`, silent-installed and probed live). Two combined lanes
(Engineering+Test: `01-eng-test-deepdive.md`; UX+Writer+QA: `02-ux-writer-qa-deepdive.md`)
on top of the per-slice audit-lites (11.1–11.5, all remediated) and the recorded live
install/verify/uninstall cycle.

**Verdict at audit: 1 Blocker / 0 Critical / 4 Major / 9 Minor / 4 Nit (+1 info).**
**After remediation: 0/0/0/0/0** — record below.

## The headline: the gate caught a real Blocker

**BG-U001 — the installer shipped no SPA and no prompt templates.** pyproject declared no
package-data, so the wheel `pip install --target` builds excluded `src/kimcad/web/` and
`src/kimcad/prompts/`; the installed window opened onto a 404 and a real (non-demo) design
would have failed on missing prompts. Masked for the project's entire history by editable
dev installs, and by every install proof exercising the API but never `/`. **Fixed:**
package-data declared; `verify_install.py` now fetches the SPA shell + a referenced asset
and checks the prompts dir, so this class can never pass silently again; the rebuilt
installer re-proven end-to-end, and the installed window verified showing the real app
(title + wizard content read out of the live window).

## Remediation record (every finding → fixed, same day)

| Finding | Fix |
|---|---|
| BG-U001 (Blocker) | Package-data + the permanent verify_install SPA/prompts checks + rebuild + live window proof (above). |
| BG-E001 (Major) | The installer-staging smoke runs in CI on EVERY push (`build_installer --stage-only` + `verify_install dist/staging`) — lock drift, strip breakage, launcher-contract moves, and pin rot now fail the gate, not the next manual build. |
| BG-U002 (Major) | Settings gained the wizard's Get-Ollama guidance AND "Run the setup walkthrough again" (clears the flag + reopens the wizard via an app event; pinned) — skipping setup is never a dead end. |
| BG-U003 (Major) | The full tag-time package written (CHANGELOG `0.9.0b1` entry incl. this Blocker's record; ROADMAP EXIT MET; README status; HANDOFF resume box; ledger row + log). Tag naming settled: BOTH `stage-11` and `beta`. |
| BG-U004 (Major) | `printproof3d-integration.md` + README corrected: the engine is bundled and ON by default in the installed beta (stable v0.5.0); from-source remains opt-in. |
| BG-E002/E003 (Minor) | The release strip rewritten on exact stems (`py` can't swallow `pydantic`), covering setuptools/_distutils_hack/pkg_resources + blanket `.pth`/`.whl`, with a hardened leftovers assertion. |
| BG-E004 (Minor) | Proven empirically: installed to `…\KimCad Spaced (x86) Test` and verify_install ALL GREEN (the earlier failure was the test harness's cmd quoting, not the installer). |
| BG-E005 (Minor) | The launcher AST test asserts BOTH halves (env + sys.path before the kimcad import) on min line numbers. |
| BG-E007 (Minor) | `test_every_runtime_dep_is_in_the_lock` — a pyproject dep missing from the lock fails every run. |
| BG-U005 (Minor) | ARCHITECTURE gained `paths.py` + `shell.py` rows and the Stage 11 additions paragraph (the read/write split). |
| BG-U006 (Minor) | The installer's final page states data retention exactly (designs NEVER removed; working data opt-in). |
| BG-U007 (Minor) | Moonraker + PrusaLink ship as visible fill-in templates (the Bambu pattern); supported-printers rows updated. |
| BG-U008 (Minor) | install-guide names .NET 4.7.2+ alongside WebView2; troubleshooting gained three installed-app entries (window won't open / SmartScreen / where-is-my-stuff). |
| BG-U009 (Minor) | Process note accepted: 11.6/11.7 were covered by THIS gate rather than per-slice audit-lites; the gate's findings on them are remediated here. |
| BG-E006 / BG-U010 / BG-U011 (Nits) | ci.sh header truthful; README's "Not a developer?" routes to install-guide; the .iss SmartScreen comment corrected. |
| BG-E008 (Info) | Recorded: pip-audit covers the shipped wheel set; the four pinned binaries (CPython embed, OpenSCAD, OrcaSlicer, PrintProof3D) are SHA-256-pinned but not CVE-scanned — a post-beta watch item. |

## What held (the lanes' positives)

All API contracts held live ON THE INSTALLED BUILD (truthful Allow headers, typed
validation, demo-mode pull refusal, write isolation); the strip/seam/lockstep remediations
from the slice audits all verified intact; the Stage-11 copy register judged the strongest
in the project; the SmartScreen doc section exemplary; version single-sourcing held on
every probed surface.

## The installed-artifact walkthrough (evidence summary)

Built (202.0 MB, SHA-256 beside it) → silent-installed (default path AND a
spaced-parenthesized path) → `verify_install` ALL GREEN on both (version via the embedded
interpreter; server; bundled OpenSCAD/OrcaSlicer; **the SPA shell + JS asset serving**;
prompts shipped; demo design rendered + mesh downloaded; `%LOCALAPPDATA%` write isolation
proven by full-tree diff) → the installed WebView2 window opened the REAL app (title
`KimCad`, the first-run wizard rendering) and closed clean → silent uninstall removed the
app completely, preserving user data. The remaining truly-clean-profile double-click run
(fresh Windows user, GUI installer, no flags) is the beta tester's first minute by design —
everything scriptable about it is proven above.
