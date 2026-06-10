# Documentation Deep-Dive — KimCad (Stage A gate)

**Audit date:** 2026-06-10
**Role:** Technical Writer
**Scope audited:** Stage A doc surface at commit `5aad7f3` — the NEW `docs/getting-started-windows.md` and `docs/troubleshooting.md` (every executable claim verified against the code), the README Setup pointer block, the `docs/README.md` index updates, and drift checks of EXISTING docs (README, ARCHITECTURE.md, CHANGELOG.md, `config/default.yaml` comments) against Stage A's code changes (typed first-run errors, fail-fast, connect-timeout split, generic 500s, ModelHealthPill).
**Writer mode:** audit-only
**Auditor posture:** Adversarial (stage gate)

---

## TL;DR

The two new non-developer docs are unusually honest and almost everything in them is true: every quoted error string, command, port, flag, file path, config key, and version pin was traced to the code and matched. The `#python-isnt-found` anchor resolves under GitHub slug rules, every internal link target exists, and the size/RAM claims are plausible against the 9.6 GB model and ~200 MB tool pins. Three Majors keep this from a clean pass: Step 3 of the getting-started walkthrough has a classic ZIP-nesting trap that will strand exactly the persona the doc exists for; ARCHITECTURE.md was not updated for Stage A's new error/retry behavior (and doesn't know `errors.py` exists); and CHANGELOG.md carries no Stage A entry at what is nominally Stage A's gate. All are cheap fixes. No doc lies about the product.

## Severity roll-up (documentation)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 3 |
| Minor | 2 |
| Nit | 2 |

## What's working

- **The error strings quoted in `troubleshooting.md` are the real ones.** "KimCad couldn't reach your local AI" is `MODEL_UNAVAILABLE_MESSAGE` verbatim (`src/kimcad/pipeline.py:181`); "the model isn't available on your local AI server" is the CLI's NotFoundError message (`src/kimcad/cli.py:514`); "OpenSCAD/OrcaSlicer isn't installed at …" is `ToolMissingError` (`src/kimcad/errors.py:28`, raised with tool names "OpenSCAD"/"OrcaSlicer" at `openscad_runner.py:294` / `slicer.py:206`); "Port 8765 is already in use" matches `webapp.py:2021`; "Your local AI isn't running yet — start Ollama" matches the Landing pill (confirmed in the Stage A walkthrough report). A user pasting a symptom into search will land on the right entry.
- **Commands, ports, and flags all check out.** `kimcad web` is a real console script (`pyproject.toml` `[project.scripts]`); default bind is `127.0.0.1:8765` and the startup line is exactly `KimCad web UI on http://127.0.0.1:8765` (`webapp.py:2004,2025`, `cli.py:87-88`); `--port 8766` is a real flag; `kimcad models` exists (`cli.py:117`); `ollama pull gemma4:e4b` matches the configured model (`config/default.yaml:56`); `python scripts\fetch_tools.py` exists, is checksum-pinned (sha256 verified, mismatch deletes the archive), and the OrcaSlicer 2.4.0-alpha / 2.3.2-CLI-crash story in troubleshooting matches both `scripts/fetch_tools.py:77-96` and the README verbatim.
- **The anchor and every link target resolve.** `troubleshooting.md#python-isnt-found` slugs correctly from the "Python isn't found" heading under GitHub's rules (apostrophe dropped, spaces → hyphens); `guide-my-designs.md`, `../SECURITY.md`, `requirements.lock`, and `config\local.yaml` (`binaries.openscad`/`binaries.orcaslicer` keys, `default.yaml:8-9`) all exist.
- **The numeric claims are plausible and hedged correctly.** Model "~5–10 GB" brackets the 9.6 GB the test fixtures use for `gemma4:e4b`; tools "about 200 MB"; "15 GB free disk" comfortably covers model + tools + venv + Ollama; "ideally 16 GB+ RAM" is a fair floor for a ~4B-effective model (the config targets 32 GB).
- **The docs match Stage A's actual UX.** "Check again" is the pill's real button (`ModelHealthPill.tsx:34`); the phase strings "Planning the shape…" / "Rendering the part…" are the CLI's exact lines (`cli.py:244,246`); the generic-500 claim ("the browser deliberately shows only a short message; the terminal has the detail") is precisely `webapp.py`'s QA-008 behavior; the photo/empty-description → outdated-Ollama entry matches the `think:false` hint in `llm_provider.py:363-381`. The vision-update reassurance "your model and settings survive the update" is consistent with how Ollama stores models.
- **The README pointer block and docs index are accurate and well-aimed.** The pointer names both new docs with correct relative paths and honestly frames the Setup section as "the developer-shaped version of the same steps"; the index entries describe the two docs exactly and put them first, where the non-developer will look.
- **Voice.** Both docs keep the project's plain-words register ("the llama icon in the system tray", "an issue report with the terminal's last lines is gold"), state the installer caveat up front, and never overclaim. This is what honest onboarding copy looks like.

## What couldn't be assessed

- Live external targets and sizes: python.org / ollama.com download pages, the OrcaSlicer GitHub release asset, the actual byte sizes and the "15–30 minutes, most of it download time" claim — verified for plausibility only, not fetched.
- Whether `gemma4:e4b` is currently pullable from the Ollama registry.
- "Ollama starts itself with Windows" — the installer's documented default, but not verifiable from this repo.
- GitHub's rendered anchor was derived by slug rule, not observed in a live render.

---

## Doc asset inventory (Stage A surface)

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| docs/getting-started-windows.md (NEW) | Yes | Strong, one trap | DOC-001, DOC-005 |
| docs/troubleshooting.md (NEW) | Yes | Strong | DOC-004, DOC-007 |
| README.md Setup pointer block | Yes | Strong | — |
| docs/README.md index updates | Yes | Adequate | DOC-006 |
| ARCHITECTURE.md (drift check) | Yes | Drifted at Stage A seams | DOC-002 |
| CHANGELOG.md (drift check) | Yes | No Stage A entry | DOC-003 |
| config/default.yaml comments (drift check) | Yes | Clean — no `timeout_s` comment exists to drift; the connect split lives in `llm_provider.py`/`config.py` comments, both accurate | — |

## Persona walk-through

**First-time non-developer (the doc's stated audience):** Succeeds through Steps 1–2 (the PATH-checkbox and Store-alias guidance is exactly the failure mode they'll hit, and the fix entry is right). Step 3 is where they're most likely to be stranded: the ZIP-extraction nesting trap (DOC-001) produces an error no troubleshooting entry covers. Steps 4 and Day-to-day are accurate and verifiable.

**Returning user:** `troubleshooting.md` is organized symptom-first with the real strings as headings — they will find their entry. One gap: the web surface's "model isn't pulled yet" phrasing isn't among the quoted symptoms (DOC-004).

**New team member:** README + ARCHITECTURE.md remain the path, and ARCHITECTURE.md now under-describes Stage A's error architecture (DOC-002) — they'd discover `errors.py` and the fail-fast probe only by reading source.

---

## Findings

### [DOC-001] — Major — Onboarding/Accuracy — Step 3's "Download ZIP → unzip to C:\KimCad → cd C:\KimCad" hits the GitHub ZIP-nesting trap

**Evidence**
`docs/getting-started-windows.md:56-66`: "Download the code as a ZIP … unzip it somewhere easy, e.g. `C:\KimCad`" followed by `cd C:\KimCad` / `pip install -r requirements.lock`.

GitHub's "Download ZIP" wraps the repo in a `<repo>-<branch>/` folder. Windows Explorer's "Extract All…" to `C:\KimCad` therefore yields `C:\KimCad\kimcadclaude-main\…`. The very next command, `pip install -r requirements.lock`, fails from `C:\KimCad` with `Could not open requirements file: … No such file or directory` — not plain words, and `troubleshooting.md` has no entry for it.

**Why this matters**
This is the highest-probability hard stop in the whole walkthrough, and it lands on exactly the persona the doc was written for (DOC-001/DOC-004 in the stage plan: the non-developer). Everything after Step 3 is unreachable for them. The doc also never names the repo URL or the expected folder contents, so the user has no way to self-diagnose ("you should now see `requirements.lock` in this folder" would have caught it).

**Blast radius**
- Adjacent docs: README's developer Setup section is unaffected (it assumes a clone). `troubleshooting.md` needs a matching symptom entry whatever the fix wording is.
- User-facing: the entire non-developer first-run funnel — Steps 3–4 and the smoke test all sit behind this.
- Tests to update: none (doc-only fix).
- Related findings: DOC-007 (the same Step-3/troubleshooting pairing).

**Fix path**
In Step 3: name the actual GitHub repo URL; state that the ZIP unpacks into a folder like `kimcadclaude-main` and to either drill into it or rename/move it to `C:\KimCad`; add a one-line success check ("you should see `requirements.lock` and a `scripts` folder"). Add a troubleshooting entry keyed on `Could not open requirements file`.

### [DOC-002] — Major — Architecture/Accuracy — ARCHITECTURE.md was not updated for Stage A's error/retry architecture

**Evidence**
- `ARCHITECTURE.md:76` (`llm_provider.py` row): "Retries connection/timeout errors so a flaky local server doesn't fail a case." Stage A (commit `d917a98`) changed this materially: a first-attempt connection error plus a failed 2 s TCP probe now **fails fast instead of retrying** (`llm_provider.py:229-241`), and the client timeout is split connect=5 s vs long read (`llm_provider.py:203-210`). The sentence as written now describes only half the policy and implies a never-started Ollama burns the ~4-minute retry budget — the exact behavior Stage A removed.
- The module map (`ARCHITECTURE.md:72-107`) has no row for `src/kimcad/errors.py`, the new shared typed-error module whose docstring explicitly declares it the single source keeping CLI and web surfaces from drifting (QA-001/QA-003).
- The `webapp.py` narrative (lines 138+) says nothing about Stage A's typed error surfaces: model-down → typed 200 status, `ToolMissingError` → typed `render_failed`, generic 500s stripped of exception class names (QA-008) — all now load-bearing behavior the new docs publicly describe.

**Why this matters**
The new-team-member persona reads ARCHITECTURE.md to learn exactly this kind of cross-cutting policy. Right now the public user docs (`troubleshooting.md`) describe the system's error behavior more accurately than the architecture doc does — an inversion that will mislead the next engineer who touches the retry loop.

**Blast radius**
- Adjacent docs: only ARCHITECTURE.md; README and the new docs are consistent with the code.
- Shared assumption: the retry/fail-fast policy is documented in three places (ARCHITECTURE row, `llm_provider.py` comments, `config.py:73-75` comment) — the code comments are accurate; only the ARCHITECTURE row lags.
- User-facing: none directly (internal doc).
- Related findings: DOC-003 (same root cause: Stage A code landed without the existing-doc sweep).

**Fix path**
Update the `llm_provider.py` row (retry-with-fail-fast + connect/read split), add an `errors.py` row to the module map, and add one sentence to the web-layer section on typed first-run errors and the generic-500 policy.

### [DOC-003] — Major — Completeness — CHANGELOG.md has no Stage A entry at the Stage A gate

**Evidence**
`CHANGELOG.md` `[Unreleased]` narrates through Stage 8.5/Stage 8; nothing for Stage A's three landed slices (typed first-run errors + fail-fast, honest wizard recap + ModelHealthPill, the two non-developer docs). Commits `d917a98`, `a7215b6`, `5aad7f3` touch no CHANGELOG line.

**Why this matters**
The project's own convention (every prior stage is changelogged and tagged) makes the gap conspicuous, and Stage A's changes are user-visible: first-run failures stop being tracebacks/4-minute hangs, the landing gains a health pill, and the project gains a non-developer install path. A returning user reading the changelog at the `stage-a` tag would see none of it.

**Blast radius**
- Adjacent docs: HANDOFF.md / RUN-LEDGER may carry the same "stage done" claim and should be updated in the same pass (not audited line-by-line here).
- User-facing: release-notes readers only.
- Related findings: DOC-002 (same missed existing-doc sweep).

**Fix path**
Add a Stage A block to `[Unreleased]` (errors/fail-fast, wizard recap + pill, the two docs) before the stage is tagged.

### [DOC-004] — Minor — Completeness — The "model isn't available" entry quotes only the CLI string; the web surfaces phrase it differently

**Evidence**
`docs/troubleshooting.md:16` heads the entry with the CLI's string ("The model isn't available on your local AI server", `cli.py:514`). The web surfaces a user is more likely on say "The model isn't pulled yet — run "ollama pull …" first." (`ModelHealthPill.tsx:27`) and "Model not pulled yet" (`FirstRunWizard.tsx:26`). Additionally, a mid-design `NotFoundError` in the web path is not specially mapped in `webapp.py` and falls through to the generic 500 — so a web user may never see either string.

**Why this matters**
The returning user searches the page for the words on their screen; the web phrasing isn't there. (The pill does carry its own fix inline, which softens this.) The unmapped web `NotFoundError` itself is a code-side gap for the engineering/QA lanes, noted here only as the reason the doc can't quote a web string for the mid-run case.

**Fix path**
Add the pill/wizard phrasing as an aliased symptom in that entry. Cross-role: consider mapping `NotFoundError` in `webapp._handle_design` to a typed status like the CLI does.

### [DOC-005] — Minor — Accuracy — "the worst case is deleting the folder and starting over" is overbroad

**Evidence**
`docs/getting-started-windows.md:101-102`. Setup also installs Python (with a PATH change), Ollama (auto-start with Windows), and a ~10 GB model under the user's Ollama store — none of which live in "the folder" or are undone by deleting it.

**Why this matters**
The reassurance ("nothing harms your PC") is fair; the reset claim isn't quite true and will confuse a user trying to reclaim 10+ GB of disk by deleting `C:\KimCad`.

**Fix path**
One clause: "…deleting the folder and starting over (Python and Ollama stay installed; `ollama rm gemma4:e4b` reclaims the model's disk space)."

### [DOC-006] — Nit — Hygiene — docs/README.md's historical example names a file that doesn't exist

**Evidence**
`docs/README.md:22-23` cites `stage-8.5-slice-5-onramps.md` as an example historical file; no such file is in `docs/` (pre-existing text, but the index was touched by Stage A and is in scope).

**Fix path**
Drop or correct the example filename.

### [DOC-007] — Nit — Accuracy — "verifies checksums and skips what's already there" slightly overstates the re-run behavior

**Evidence**
`docs/troubleshooting.md:47-48` vs `scripts/fetch_tools.py:185-186`: when the tool's exe already exists the script skips entirely (no checksum re-verification of what's on disk); checksums are verified at download time only.

**Fix path**
"— it re-downloads and checksum-verifies anything missing, and skips what's already in place" (or leave; the safety claim itself is true).

---

## Drafts produced

Writer mode is audit-only; no drafts produced in this pass.

## Marketing / honesty audit

The new docs are notably honest: the "until the one-click installer ships" caveat is up front, "the AI runs on your CPU — a real design takes a few minutes" sets expectations instead of hiding them, and the STL-fallback entry tells the user their part is still fine rather than dramatizing. The README pointer block doesn't oversell either. No overclaim findings.

## Patterns and systemic observations

- **The Stage A doc work covered the NEW surface excellently and skipped the EXISTING-doc sweep.** All three Majors share that root: the walkthrough trap aside, nothing in the new docs is wrong — but ARCHITECTURE.md and CHANGELOG.md weren't reconciled with the Stage A code they describe. A one-item checklist ("grep existing docs for behavior this slice changed") would have caught DOC-002/003.
- Out-of-scope pre-existing drift observed in passing, for a future sweep: the ARCHITECTURE `llm_provider.py` row says "Four jobs" but the Provider protocol now carries five (it omits `describe_sketch`, present in code); ARCHITECTURE/`default.yaml` comments say "KimCad runs on 3.14" while README/the new doc standardize on the Python 3.13 lockfile environment — worth one reconciling pass.

## Appendix: docs reviewed

`docs/getting-started-windows.md`, `docs/troubleshooting.md`, `README.md` (Setup + web sections), `docs/README.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `config/default.yaml` (comments), `SECURITY.md` (existence), `docs/guide-my-designs.md` (existence). Code consulted for claim verification: `src/kimcad/{cli,errors,pipeline,webapp,llm_provider,config,openscad_runner,slicer}.py`, `scripts/fetch_tools.py`, `pyproject.toml`, `frontend/src/components/{ModelHealthPill,FirstRunWizard,Landing,ExportPanel}.tsx`, `frontend/src/designPhase.ts`, commits `d917a98`, `a7215b6`, `5aad7f3`.
