# Audit-lite — Stage 11 Slice 11.4 (the dev/installed paths seam) — 2026-06-10

**Scope:** Commit `5c8de96` only — `src/kimcad/paths.py` (the KIMCAD_INSTALL_ROOT seam),
`config.PROJECT_ROOT` routed through it, webapp/shell web roots + the CLI's installed-mode
relative `--out`, the always-per-user WebView2 profile, plus the 11.3-audit lockstep fixes
(package-lock + the PEP 440 ↔ npm-semver tripwire and the `/D`-define forward guard).

**Auditor stance:** independent single pass; directed hunts: import-time env capture,
seam-bypassing `PROJECT_ROOT` copies, the dev `writable_root == repo root` behavior change,
the LOCALAPPDATA fallback, and the lockstep version-mapping regex.

**Verification actually run (this audit, this box):**

| Check | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest tests/test_paths.py tests/test_version_single_source.py tests/test_shell.py -q` | **17 passed** in 8.12s |
| `.venv\Scripts\python.exe -m ruff check .` | **All checks passed** |
| `ruff format --check` (informational) | 71 files project-wide diverge incl. 4 of this commit's — format is not this project's gate ("ruff clean" = `ruff check`); not a finding |
| HEAD == audited commit | yes (`5c8de96`, clean tree for tracked files) |

## Severity rollup

| Blocker | Major | Minor | Nit | Info |
|---|---|---|---|---|
| 0 | 1 | 2 | 2 | 1 |

## Findings

### FINDING-001 — Major — `cadquery_runner.py` keeps its own `PROJECT_ROOT` (seam BYPASSED) — the plan's own 11.4 modify-list item, and the commit message claims it's routed
`src/kimcad/cadquery_runner.py:64` still computes `PROJECT_ROOT = Path(__file__).resolve().parents[2]`
and uses it at `:310` to find the worker venv (`PROJECT_ROOT / ".venv-cq313" / "Scripts" / "python.exe"`,
the highest-priority Windows probe in `find_cadquery_interpreter`). It does **not** import the
seam-routed `kimcad.config.PROJECT_ROOT` (contrast `openscad_runner.py:33`, which does and is
therefore correctly routed at `:36` `LIBRARY_DIR` and `:245` `env_path`). Three strikes:
1. **The plan names it.** `.claude/plans/stage-11-installer-beta.md:144` — Slice 11.4 modify list:
   "`cadquery_runner.py` (worker venv discovery under install root)". Not touched by this commit.
2. **The commit message claims it.** "reads (config templates, tools/, **the worker venv** —
   everything PROJECT_ROOT-relative) resolve under the install root" — for the worker venv that is
   false; its resolution never consults `KIMCAD_INSTALL_ROOT`.
3. **It violates paths.py's own contract.** "Nothing else may infer installedness — one switch,
   set in one place, **testable by setting one env var**." Setting `KIMCAD_INSTALL_ROOT` in a test
   moves `config.PROJECT_ROOT` (on fresh import) but not `cadquery_runner.PROJECT_ROOT`.
Mitigating: under the *planned* 11.5 layout (`pip install --target <install>\site-packages`),
`parents[2]` of `site-packages\kimcad\cadquery_runner.py` happens to equal the install root, so
the bundled-venv probe would coincidentally work — but that's layout-coupled luck, breaks the
moment 11.5 nests the package one level differently, and is exactly the divergence the seam
exists to prevent. **Fix directive:** `from kimcad.config import PROJECT_ROOT` (one line, mirrors
openscad_runner), or have the probe call `paths.install_root()` directly. One slice before 11.5
freezes the layout is the cheap moment.

### FINDING-002 — Minor — `llm_provider.py:41` `LIBRARY_DIR` recomputes `parents[2]` (seam bypassed for the library-manifest read)
`LIBRARY_DIR = Path(__file__).resolve().parents[2] / "library"` feeds
`build_library_manifest` (`:186`) — a real-LLM-mode read of `library/manifest.yaml`. The plan's
11.4 line is "**Every** current `PROJECT_ROOT`-relative read/write routed through it"; this one
wasn't (and `openscad_runner` has a *second*, seam-routed `LIBRARY_DIR` — the two can now
disagree). Same coincidental-layout mitigation and same one-line fix as FINDING-001.

### FINDING-003 — Minor — Planned seam surface dropped without a stated decision: `tools_dir()` / `user_config_path()` never created, `fetch_tools.py` targets unrouted; installed `local.yaml` lands under read-only Program Files
The plan (`stage-11-installer-beta.md:139-145`) promises `tools_dir()`, `user_config_path()`, and
routing "`fetch_tools.py` targets". Shipped `paths.py` has neither function; `scripts/fetch_tools.py:34`
still writes `parents[1]/tools` (repo root). Consequences, graded honestly:
- `tools/` reads are fine — they resolve via the routed `config.PROJECT_ROOT` (`config.py:151/167`),
  so a dedicated `tools_dir()` was arguably redundant. OK.
- `settings_store.py` (also on the modify list) needed no change — `~/.kimcad` is per-user in both
  modes. OK, and `paths.py`'s docstring says so.
- **Not OK silently:** `LOCAL_CONFIG = PROJECT_ROOT / "config" / "local.yaml"` (`config.py:26`) means
  the installed app's only config-override location is inside Program Files — unwritable by the
  user. And if 11.5's "CadQuery fetch-on-demand" decision lands, a runtime `fetch_tools` would try
  to write `<repo-root-shaped>/tools` from a read-only install. Neither bites in this commit, both
  bite in 11.5/11.6. **Fix directive:** record the decision in the plan (drop `tools_dir()`, defer
  `user_config_path()` to 11.5 with the installed local-config story), or add `user_config_path()`
  now; route `fetch_tools.py` if and only if it's promoted to a runtime path.

### FINDING-004 — Nit — `bench`/`bakeoff` relative `--out` defaults are not routed in installed mode
`cli.py:124/164` default to `output/bench` / `output/bakeoff` and `:395/:441` use `Path(args.out)`
bare — the same Program-Files-CWD hazard the `design` fix (`cli.py:327-332`) closes. Dev-only
commands realistically, but the asymmetry is one `if is_installed()` away from gone (or hoist the
design-path resolution into a tiny shared helper next to `writable_root`).

### FINDING-005 — Nit — The lockstep mapping regex covers only `bN`; the first `rc`/`a`/`.postN` bump fails the test instead of mapping
`tests/test_version_single_source.py` `re.fullmatch(r"(\d+\.\d+\.\d+)b(\d+)", declared)` —
multi-digit betas are handled correctly (`b12` → `-beta.12`; verified against the regex). But
`0.9.0rc1` (the plausible next bump) falls through to `expected = declared`, asserting
`package.json["version"] == "0.9.0rc1"` — not valid npm semver, so the test fails at the bump.
It fails **closed and loudly** (nobody ships a silent mismatch), hence Nit not Minor — but the
failure message will say "wrong version" when the truth is "the mapping is too narrow". Extend to
`(a|b|rc)` → `-alpha./-beta./-rc.` when convenient.

### FINDING-006 — Info — "Dev behavior is byte-identical" is true only for CWD == repo root: the web server's default `web_root` moved from CWD-relative to repo-rooted
`webapp.py:2274` / `shell.py:92` previously resolved `output/web` against the CWD; now
`output_dir()` pins it to the repo root in dev. Hunted for dependents: **none** — every test
passes `out_root`/`tmp_path` explicitly (`test_webapp.py`, `test_first_run_errors.py:307`,
`test_connections_api.py`, `test_bakeoff.py`), README's `output/` mention (`:199`) assumes a
repo-root launch, prior QA audits launched from repo root. A dev launching `kimcad web` from
elsewhere sees output move into the checkout — an *improvement* (it's where the docs say it is),
just not byte-identical as claimed. No action beyond this note.

## Directed hunts that came back clean (verified, not assumed)

- **Import-time capture (hunt 1): no in-repo violator.** `KIMCAD_INSTALL_ROOT` appears only in
  `paths.py`, `config.py` (comment), and `tests/test_paths.py` — and the tests monkeypatch it only
  around the *lazy* `paths.*` functions, with `test_config_read_paths_follow_the_install_root`'s
  docstring explicitly acknowledging that `config` captures `PROJECT_ROOT` at import and can't be
  re-tested post-import. The shell, webapp, and CLI never set the env var; the launcher contract
  ("before Python starts") holds everywhere in-tree. Residual (accepted): lazy `paths.*` vs
  import-captured `config.PROJECT_ROOT` *would* diverge if anything ever set the var mid-process —
  FINDING-001's fix keeps that class closed by construction.
- **`is_installed` empty-string handling:** `bool(os.environ.get(...))` and `install_root`'s
  truthiness check agree — `KIMCAD_INSTALL_ROOT=""` is dev in both. Consistent.
- **LOCALAPPDATA fallback (hunt 4): sane.** `os.environ.get("LOCALAPPDATA") or Path.home()/"AppData"/"Local"`
  is the conventional Windows fallback; `LOCALAPPDATA` is effectively always set, the fallback
  lands per-user, and `test_installed_mode_without_localappdata_still_lands_per_user` pins it.
- **CLI installed `--out` (design):** relative `--out` → `writable_root()/out`, default `output`
  → `%LOCALAPPDATA%\KimCad\output` — consistent with `output_dir()`. Dev CWD-relative behavior
  preserved as documented.
- **WebView2 profile:** per-user in every mode; `test_dev_mode_is_the_repo_root` asserts the repo
  is not a parent of the profile dir. SHELL-005 genuinely closed.

## Escalation verdict

**No escalation to audit-team.** The seam's shape is right, the tests pin the installed half, and
both 11.3 carry-fixes are real (lock regenerated, lockstep + `/D`-define guards enforced). But
this slice's one job was "grep `PROJECT_ROOT` and route each" (the plan's own words), and the grep
finds two unrouted copies — one of them (`cadquery_runner`, FINDING-001) named in the plan's
modify list and claimed routed by the commit message. Per the standing 0/0/0/0/0 rule: fix all six
(FINDING-001 and -002 are one import line each) **before Slice 11.5**, which is the slice that
freezes the physical layout the current coincidence depends on.
