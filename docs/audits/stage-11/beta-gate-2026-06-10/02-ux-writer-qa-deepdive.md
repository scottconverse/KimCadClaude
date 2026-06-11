# Stage 11 BETA GATE — UI/UX + Technical Writer + QA deep-dive

- **Date:** 2026-06-10
- **Scope:** the Stage 11 diff `07fb3ad..7f8b0d3` (slices 11.1–11.7), the user-docs set, and the
  INSTALLED artifact at `C:\Users\scott\AppData\Local\Temp\kimcad-install-test` (run live).
- **Auditor:** Claude (combined UX / writer / QA lane; read-only on the product tree).
- **Per-slice audit-lites (11.1–11.5):** read, not re-reported. Remediations spot-verified —
  FINDING-002 (launcher `sys.dont_write_bytecode` + `PYTHONDONTWRITEBYTECODE`, `kimcad_launcher.py:27-28`,
  plus the widened `[UninstallDelete]` in `kimcad.iss:60-61`) ✓; FINDING-003 (full-tree snapshot diff,
  `verify_install.py:59-61,109-113`) ✓; FINDING-006 (explicit `AppVersionQuad`, `build_installer.py:210-211`
  + `kimcad.iss:21`) ✓; FINDING-007 (.NET 4.7.2+ named in the shell's friendly error, `shell.py:142-146`) ✓.

## Severity rollup

| Blocker | Critical | Major | Minor | Nit |
|---|---|---|---|---|
| **1** | 0 | **3** | **5** | **2** |

---

## BG-U001 (Blocker) — the installer ships NO UI: the SPA is missing from the staged tree and the installed artifact; the installed app serves 404 at `/`

**Run for real.** Started the installed app's own server
(`{app}\python\python.exe {app}\kimcad_launcher.py web --demo --port 8746`):

- `GET /` → **404** (empty body). `GET /index.html` → 404. `GET /assets/kimcad.js` → 404.
- `C:\Users\scott\AppData\Local\Temp\kimcad-install-test\site-packages\kimcad\` contains **no `web/`
  directory at all** (every `.py` module is present; `index.html`/`kimcad.js` exist nowhere in the
  install tree — only OrcaSlicer's own resource pages match a recursive search).
- Same at the **source**: `dist/staging/site-packages/kimcad/` on the build box has no `web/` either —
  the defect is in the build, not the install copy.

**Root cause.** `build_installer.stage_site_packages()` installs kimcad via
`pip install --target … --no-deps --upgrade <repo>` (`scripts/build_installer.py:111-115`). `pyproject.toml`
uses `[tool.setuptools.packages.find] where=["src"]` with **no package-data declaration and no
MANIFEST.in** — `src/kimcad/web/` (no `__init__.py`, non-Python files) is silently excluded from the
wheel. Dev installs are editable (`pip install -e .`), so dev serving reads `src/kimcad/web/` directly
(`webapp.py:44 WEB_DIR = Path(__file__).parent / "web"`) and every dev-tree proof (11.1's live window,
11.6's wizard run) passed while the artifact was hollow.

**Why every prior gate missed it.** `scripts/verify_install.py` checks `--version`, `/api/health`,
`/api/design`, the mesh download, and the writes seam — it **never fetches `/`** (lines 64-103). The
windowed app installed from this artifact opens a WebView2 window onto a blank 404: the Start-Menu
shortcut, the desktop icon, and the `[Run]` "Launch KimCad now" postinstall all land there. The beta,
as built, has no usable product surface.

**Fix directive.** (a) Declare the SPA as package data
(`[tool.setuptools] include-package-data` + `[tool.setuptools.package-data] kimcad = ["web/**"]`, or a
MANIFEST.in graft) so the wheel carries `kimcad/web/`; (b) add `GET /` (assert 200 + `text/html` +
a known SPA marker string) and one `/assets/` fetch to `verify_install.py` so this class of hole can
never pass again; (c) extend `tests/test_build_installer.py` with a staged-tree assertion that
`site-packages/kimcad/web/index.html` exists; (d) rebuild, reinstall, re-verify, and re-run the
windowed shell from the real install before tagging.

## BG-U002 (Major, UX) — the clean-box "skip setup" path is a dead end: the wizard never reopens, and Settings assumes Ollama is installed

The first-run journey order is right (installer → SmartScreen guidance in the doc → shortcut →
shell → wizard), and the wizard's Slice-11.6 copy is the best version of this line in the product
("Don't have it yet? **Get Ollama** — install it, let it start, then **check again**. Already
installed? Just start it. You can finish setup either way." — `FirstRunWizard.tsx:344-366`, opened
via the `openExternal` bridge, http(s)-only ✓). But on a truly clean box where the user **skips**:

- "Skip setup" / Escape sets `localStorage kc-first-run-done=1` (`App.tsx:88-95`); there is **no
  "run setup again" affordance anywhere** (grep over `frontend/src`), and the shell's stable port +
  persistent WebView2 profile (correct for SHELL-001) guarantee the flag survives every relaunch.
- Settings' AI-model card says only "**Ollama isn't running. Start it**, then check again"
  (`SettingsPanel.tsx:332-337`) — no Get-Ollama link, and it cannot distinguish not-installed from
  not-running (the exact gap 11.6 fixed in the wizard).
- The model-not-downloaded line points at "the setup wizard's Download button"
  (`SettingsPanel.tsx:338-344`) — a venue the skipper can no longer reach — with the only other path
  a terminal command (`ollama pull …`), contradicting the installer doc's "No terminal, no Python"
  promise (`docs/install-guide.md:3-4`).

**Fix directive.** Smallest honest fix: mirror the wizard's 11.6 action line into the Settings model
card (Get Ollama button via `openExternal` + the installed-vs-running wording), and either surface the
in-app download there too (`/api/model-pull` is venue-agnostic) or add a "Run setup again" link in
Settings that clears `kc-first-run-done` and remounts the wizard. Any one of these breaks the loop;
the pair makes Settings self-sufficient.

## BG-U003 (Major, writer) — the tag-time package owed at `beta` does not exist yet: exact lines

Enumerated against HEAD `7f8b0d3` (every line verified by grep/read):

| Artifact | Stale/missing line(s) | What's owed at the tag |
|---|---|---|
| `CHANGELOG.md` | `### Added` under `[Unreleased]` starts at Stage 10 (line ~28); **no Stage 11 entry at all** | the Stage 11 section: shell, connections card, version normalization, paths seam, installer, Ollama guide bridge, PrintProof3D bundling + dispositions, user-docs set; then the `0.9.0b1` release section cut at the tag |
| `ROADMAP.md` | line 73 "**Next = Stage 11 (Windows installer + …**"; the Stage 11 section (line 319) has **no `EXIT MET` block** (Stage 10's, line ~313, is the house pattern) | EXIT MET (2026-06-10) with the dispositions (PrintProof3D bundled; CI re-enable superseded by owner decision; CadQuery not shipped) |
| `README.md` | lines 35-36 "Next up: the Windows installer + beta gate (Stage 11, final)." | re-point to "the beta is installable — `docs/install-guide.md`" |
| `HANDOFF.md` | line 6 "**Next = Stage 11 (Windows installer + beta gate, FINAL)**" | the post-beta handoff (next = real hardware at Kim's) |
| `docs/audits/RUN-LEDGER-2026-06-05.md` | line 25 and line 61: Stage 11 rows all `☐` (note both say tag `stage-11`; ROADMAP says tag **`beta`** — reconcile) | check the boxes, record the gate, settle the tag name |

None of these may be written before the gate verdict — but the tag cannot happen without them, and
BG-U001 blocks the tag anyway.

## BG-U004 (Major, writer) — `docs/printproof3d-integration.md` says the engine "is off by default — the binary isn't fetched"; the beta ships it ON

`docs/printproof3d-integration.md:29`: "The engine is **off by default** — the path is configured but
the binary isn't fetched, so KimCad…" and the whole "how to enable" section (lines 36-45) instructs
building from the Rust repo. Overturned by Slice 11.7: the installer stages pinned v0.5.0 at
`tools/printproof3d/printproof3d.exe` (`build_installer.py:151-161`; verified present in the installed
artifact; `verify_install.py:44-46` asserts it). A beta user reading this doc will believe their
readiness card is gate-only when it is engine-backed. Related softer instance: `README.md:57-60`
"when it's configured, the **optional** arm's-length PrintProof3D" — true for from-source, wrong as
the resting description of the shipped beta. **Fix:** rewrite the integration doc's status paragraph
(bundled + on by default in the installed beta; from-source users still fetch/build; degradation
posture unchanged) and add one clause to the README sentence.

## BG-U005 (Minor, writer) — ARCHITECTURE.md's module map ends at Stage 10; the Stage-11 seam that moves every write is undocumented

`ARCHITECTURE.md` has rows through `design_registry.py` (Stage 9) and `model_pull.py`/`bambu_connector.py`
(Stage 10), but **no rows for `shell.py` or `paths.py`**, and line 201 still describes serving as
repo-relative. `paths.py` changes where *all* writes land when installed (`%LOCALAPPDATA%\KimCad`,
user overlay at `…\config\local.yaml`) — exactly the kind of invariant ARCHITECTURE exists to state.
**Fix:** two module-map rows + one paragraph on the dev/installed seam (`KIMCAD_INSTALL_ROOT` is THE
switch) and the shell's stable-port/profile contract.

## BG-U006 (Minor, UX/copy) — the installer's final page misstates the data-retention split the uninstaller actually implements

`installer/kimcad.iss:76-77` (final wizard page): "designs and settings live in your user folder
(**Documents-level**, not Program Files), and uninstalling KimCad **leaves them unless you say
otherwise**." Two problems against the code three screens later (`kimcad.iss:95-99`) and
`docs/install-guide.md:29-32`:

1. Saved designs/settings (`~/.kimcad`) are **never** removable by the uninstaller — "unless you say
   otherwise" wrongly implies the opt-in removal covers them; it covers only `%LOCALAPPDATA%\KimCad`
   (working output + browser profile), and the uninstall MsgBox itself says `.kimcad` is "NOT touched
   either way."
2. "Documents-level" is a mis-gloss — `~/.kimcad` is a hidden-style folder in the user-profile root,
   not in Documents; a user told "Documents-level" will look in Documents and not find it.

**Fix:** one-sentence rewrite of the final page: settings + saved designs stay in your user profile
and the uninstaller never touches them; working files in `%LOCALAPPDATA%\KimCad` are offered for
removal at uninstall.

## BG-U007 (Minor, writer) — `supported-printers.md` lists `moonraker`/`prusalink` as direct-send connections, but the shipped config has them commented out with no UI path to enable

`docs/supported-printers.md:28-29` presents both as available rows in "Direct-send connections."
`config/default.yaml:189-196` ships them **commented out**; the live `/api/connections` on the
installed artifact returns only `mock`, `octoprint`, `bambu_p2s`, `bambu_a1` — so the Settings →
Printer connections card (which renders only existing connector entries) can never show them, and
enabling one requires hand-editing a YAML overlay (terminal-adjacent work the install guide promises
away). **Fix:** either ship the templates visible-but-unconfigured like the Bambu pair, or add a
"config-file only in this beta" note to those two rows.

## BG-U008 (Minor, writer) — the Win10/WebView2 requirements line vs `shell.py`'s error copy; troubleshooting.md has no installed-app section

`docs/install-guide.md:48-50` claims Windows 10 works "with the WebView2 Runtime, which Microsoft
ships automatically via Edge" — implying nothing to do — while `shell.py:142-146`'s friendly error
says the opposite for the same situation ("on older Windows, **install** 'WebView2 Runtime' from
Microsoft") and additionally requires **.NET Framework 4.7.2+**, which the requirements line never
mentions (Win10 < 1803 lacks it). And `docs/troubleshooting.md` — which `install-guide.md:54` promises
"covers every known snag" — contains **zero** installed-app entries: no SmartScreen, no WebView2/.NET,
no blank-window, no per-user-vs-admin install snags (grep: only a Python-PATH "installer" hit, from
the from-source path). **Fix:** align the requirements line with shell.py's copy (name .NET 4.7.2+ /
Win10 1803+ or state a Win11 floor), and add an "Installed beta" section to troubleshooting.md
(SmartScreen, blank window → WebView2/.NET, uninstall data questions).

## BG-U009 (Minor, process) — slices 11.6 and 11.7 shipped without per-slice audit-lites

`docs/audits/stage-11/` holds audit-lites for 11.1–11.5 plus the dispositions file only. The pinned
cadence (HANDOFF.md:6: "Each: per-slice audit-lite → stage gate") was broken for the external-link
bridge/Ollama-guide slice (11.6, commit `1a86a2e`) and the PrintProof3D-bundling/user-docs slice
(11.7, commit `7f8b0d3`) — and 11.7 is precisely where BG-U004/U007 (docs) live and 11.5/11.7's
rebuilds are where BG-U001 (artifact) lives. This gate covers them now; record the gap so the ledger
stays honest about what got per-slice scrutiny.

## BG-U010 (Nit, writer) — README's "Not a developer?" pointer routes non-developers to the from-source walkthrough

`README.md:99-101` sends non-developers to `docs/getting-started-windows.md`, but that page now opens
by deferring to the installer (its own banner) and `docs/README.md:6` names `install-guide.md` as
"**Start here.**" One link swap (+ keep getting-started as the from-source alternative).

## BG-U011 (Nit, copy) — the `.iss` `[Code]` comment promises "the SmartScreen reality" on the final page; the page never mentions SmartScreen

`kimcad.iss:69-70` comment vs the actual `CreateOutputMsgPage` copy (models + data locations only).
The omission is arguably right — by the time this page shows, SmartScreen has already been passed,
and the real guidance lives correctly in `install-guide.md:7-19` — but the comment then documents
copy that doesn't exist. Fix the comment (or add the line if release-page guidance is wanted in-product).

---

## QA runtime evidence (the installed artifact, run live)

Server: `{app}\python\python.exe {app}\kimcad_launcher.py web --demo --port 8746` (PID 14560;
started, abused, then killed — confirmed down by a refused probe).

| Probe | Result |
|---|---|
| `GET /api/health` | 200 `{"version": "0.9.0b1", "openscad": true, "orcaslicer": true}` — single-source version holds on the installed build |
| `GET /` , `/index.html`, `/assets/kimcad.js` | **404 / 404 / 404** → BG-U001 |
| `POST /api/health` | **405**, `Allow: GET, HEAD` (truthful per-path Allow ✓) |
| `DELETE /api/settings` | 405, `Allow: GET, HEAD, POST` ✓ |
| `GET /api/model-pull` | 405, `Allow: POST` ✓ |
| `POST /api/model-pull` (demo) | 400 typed: `{"status":"not_local","error":"Demo mode doesn't download models — run KimCad without --demo…"}` — **no download started** ✓ |
| `GET /api/connections` | 200; 4 connections; `mock` flagged `simulated:true`; per-piece notes intact |
| `POST /api/connections` `use_ams:"yes"` | 400 typed (`use_ams must be true or false.`) ✓ |
| `POST /api/connections` unknown field | 400 typed (`Unknown connection field(s)…`) ✓ |
| `POST /api/connections` 250-char base_url | 400 typed (length cap) ✓ |
| `POST /api/connections` malformed JSON | 400 `Request body isn't valid JSON.` ✓ |
| `POST /api/connections` unknown name | 404 `There's no printer connection by that name.` ✓ |
| Valid save → re-read | 200 `{"saved": true}`; value round-tripped; **then reverted to the original** (`http://127.0.0.1:5000`) — confirmed restored |
| `GET /api/design` | 405, `Allow: POST` ✓ |
| `POST /api/design` (demo prompt) | 200, mesh served (1284 bytes, demo-sized); writes landed under `%LOCALAPPDATA%\KimCad\output\web` (the 11.4 seam routing, live) ✓ |

The API contracts all hold on the installed build; the product's only gap is that the UI those
contracts serve isn't in the box (BG-U001).

## What's good (so it doesn't get lost)

- The Stage-11 copy set is the most consistent register in the project: the wizard's Ollama line,
  the ConnectionsCard's "named below — so it never sits in a settings file" secret handling, the
  SendPanel's venue-honest hints all now naming a venue that exists, the reset's disclosed blast
  radius, and the supported-printers doc's API-validated/metal-validated honesty key.
- `install-guide.md`'s SmartScreen section is exemplary: states why (unsigned, cost), the exact
  click path, and the checksum verification with a copy-able command.
- The first-run journey ORDER is right, and the installer final page's "13 GB" matches the wizard's
  "Download now (~13 GB)" and the guide's "about 13 GB total"; "20 GB free" is honest headroom over
  ~1.5 GB payload + 13 GB models.
- `getting-started-windows.md`'s rewrite cleanly demotes itself to the from-source path and removes
  the stale "until the installer ships" heads-up; `docs/README.md`'s index re-orders correctly.

## Top 3

1. **BG-U001** — the installer ships no SPA; the installed app is a 404 behind a window. Fix the
   packaging, teach `verify_install.py` to fetch `/`, rebuild, re-verify. Nothing tags before this.
2. **BG-U002** — skip-setup on a clean box strands the user: no wizard re-entry, Settings assumes
   Ollama exists, terminal-only fallback against a "no terminal" promise.
3. **BG-U003** — the tag-time docs package (CHANGELOG Stage 11 entry, ROADMAP EXIT MET, README/HANDOFF/
   ledger lines) doesn't exist yet; exact lines enumerated above, plus the `stage-11` vs `beta` tag-name
   discrepancy between the ledger and ROADMAP.
