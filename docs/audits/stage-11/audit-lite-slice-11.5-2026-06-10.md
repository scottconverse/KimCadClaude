# Audit-lite — Stage 11 Slice 11.5 (the Windows installer)

- **Date:** 2026-06-10
- **Commit:** `f720cfe` ("Stage 11 Slice 11.5: the Windows installer - built, installed, verified, uninstalled on this box") + launcher from `3265ae7`
- **Scope:** `scripts/build_installer.py`, `installer/kimcad.iss`, `installer/kimcad_launcher.py`, `scripts/verify_install.py`, `tests/test_build_installer.py`, plus the REAL staged tree at `dist/staging/` (inspected directly)
- **Auditor:** Claude (read-only, single pass)

## Verification run by the auditor

| Check | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest tests/test_build_installer.py -q` | **4 passed** in 0.04s |
| `ruff check` on the four new files + launcher | **All checks passed** |
| `dist/staging/site-packages` contents inspected | findings below |
| Real artifact present | `KimCad-Setup-0.9.0b1.exe` (210,938,057 bytes) + `.sha256` |

## Severity rollup

| Blocker | Critical | Major | Minor | Nit |
|---|---|---|---|---|
| 0 | 0 | **1** | **2** | **4** |

---

## FINDING-001 (Major) — the dev-toolchain strip is mostly cosmetic; the release ships ~36+ MB of dev tooling

`build_installer.stage_site_packages()` strips `("pytest", "ruff", "pip_audit", "coverage")` via `target.glob(f"{unwanted}*")` — **top-level name prefixes only**. Inspected the real `dist/staging/site-packages` (the exact tree inside the shipped 210.9 MB exe):

- **`bin\ruff.exe` — 32.2 MB** survives (`--target` puts console scripts under `bin/`, which no glob touches), alongside `pytest.exe`, `py.test.exe`, `coverage.exe`, `coverage3.exe`, `coverage-3.13.exe`, `wheel.exe` stubs (~108 KB each).
- **`_pytest/` (2.8 MB)** survives — pytest's actual code lives in `_pytest`, which `pytest*` does not match. Only the trampoline `pytest/` dir and dist-info were removed, leaving an import-broken husk.
- pytest's dependency closure ships whole: `pluggy/`, `iniconfig/`, `pygments/` (none are runtime deps of kimcad).
- `a1_coverage.pth` (coverage's subprocess hook) ships. Inert at runtime (the launcher adds site-packages via `sys.path.insert`, not site processing, and the hook is env-gated + try/except), but it is dev residue referencing a deleted package.
- `pip_audit` is **not in `requirements.lock` at all** — that strip entry is a no-op (harmless, but signals the list was written from intent, not from the lock).
- Cosmetic riders: zero-byte stray `numpy-2.2.6-...whl` / `scipy-1.17.1-...whl` files, plus `setuptools`/`wheel`/`_distutils_hack`/`distutils-precedence.pth`.

The commit message's "dev toolchain stripped" claim is therefore materially false. Root cause: `requirements.lock` is the **dev** lock (pytest, pytest-cov, coverage, ruff are first-class entries) and a prefix-glob can't subtract a dependency closure.

**Fix directive:** install the release tree from the runtime dependency set (a `requirements-runtime.lock`, or `pip install --target ... .` letting pyproject's runtime deps resolve), instead of dev-lock-then-strip. At minimum: delete `bin/` wholesale (nothing in it is used — the launcher is the only entry point), add `_pytest`, `pluggy`, `iniconfig`, `pygments`, `a1_coverage.pth`, `*.whl`, `setuptools*`, `wheel*`, `_distutils_hack`, `distutils-precedence.pth` to the strip, and have the staging smoke assert the strip held (e.g. `import _pytest` fails under the embedded interpreter). Rebuild + re-verify after.

## FINDING-002 (Minor) — `[UninstallDelete]` covers one `__pycache__` path out of 415; the clean uninstall was by-construction luck, not coverage

The real staged tree contains **415 `__pycache__` directories** (pip compiles bytecode at `--target` install time). Because they're part of the staged payload, Inno installs them, logs them, and the uninstaller removes them — **that** is why the real uninstall was clean, not the single `{app}\site-packages\__pycache__` entry (which covers only the top-level dir, itself also already payload-tracked).

The residual risk on a long-lived **per-user** install (writable `{app}`): any *runtime-written* pyc not in the payload orphans its directory tree at uninstall. Today that window is narrow (Inno preserves source mtimes, so shipped pyc stay valid against shipped sources), but it opens the moment anything invalidates a pyc or imports a source file pip didn't compile. The `.iss` comment ("__pycache__ trees the runtime writes … cheap to clean") describes the intent; the single non-recursive path doesn't implement it — Inno wildcards don't recurse mid-path.

**Fix directive:** belt and suspenders — (a) in `kimcad_launcher.py`, set `sys.dont_write_bytecode = True` and `os.environ["PYTHONDONTWRITEBYTECODE"] = "1"` (the env var covers the worker-venv/tool subprocesses) so runtime never writes pyc into `{app}`; (b) widen the entry to `Type: filesandordirs; Name: "{app}\site-packages"` — that tree is wholly app-owned (user data lives in `%LOCALAPPDATA%\KimCad` and `~/.kimcad`), so deleting it at uninstall is safe and makes orphaning structurally impossible.

## FINDING-003 (Minor) — verify_install's "install dir untouched" check tests one directory, not the claim

Contract 5 prints "install dir untouched" after checking exactly `{app}\output`. Writes anywhere else in the install tree — `config/local.yaml` (the pre-11.4 regression this seam exists to prevent), `site-packages/**/__pycache__`, `tools/` — would pass undetected. Given FINDING-002, runtime pyc writes into site-packages are currently *possible* and this check would bless them.

**Fix directive:** snapshot the install tree (path → mtime/size) before the server run and diff after; fail on any change. Cheap (one walk), stdlib, and turns contract 5 into what the green banner claims. Optional same-file nits, fold in while there: compare `health["version"]` to the `--version` output (it's fetched, printed, never asserted), and pre-check the port with a bind probe for a clearer failure than the 60 s timeout (`--port` already exists as the escape hatch — not a defect, just diagnosability).

## FINDING-004 (Nit) — per-user install = user-writable app dir: disclose the tradeoff

With `PrivilegesRequiredOverridesAllowed=dialog`, a non-admin choice lands the app in `%LOCALAPPDATA%\Programs\KimCad`: `kimcad_launcher.py`, `site-packages/`, and `python/` (DLLs) are then writable by any same-user process — the classic per-user-install planting surface. Judgment: **acceptable as designed**. There is no privilege boundary crossed (anything that can tamper already runs as the user), `{autopf}` (Program Files, admin) is already the default offered first, and this matches industry practice (VS Code's user installer makes the same trade). The launcher's `sys.path.insert(0, site-packages)` is correct for the layout; `{app}` itself stays on `sys.path` as the script dir but carries no shadowable `.py` besides the launcher.

**Recommendation:** one disclosure line in the install docs/README ("the per-user option installs to a user-writable folder; choose the default Program Files install on shared machines") — no code change.

## FINDING-005 (Nit) — the 3.13.13 embeddable pin has no staleness policy

`PY_EMBED_URL`/`PY_EMBED_SHA256` are pinned (good — HTTPS + SHA-256 verified before unzip) and the test guards the `3.13` line, but nothing says when or how the micro version bumps. **Fix:** a two-line comment beside the pin: bump in lockstep with the dev venv interpreter (the "same interpreter line the suite proves" invariant), recompute the SHA from python.org, and let `test_build_script_version_matches_pyproject` keep the line honest.

## FINDING-006 (Nit) — `VersionInfoVersion` is left to Inno's derivation from `0.9.0b1`

`AppVersion={#AppVersion}` carries the PEP 440 string; `VersionInfoVersion` is unset, so Inno derives the EXE's file-version metadata from the leading numeric portion. The real compile succeeded, so the derivation is tolerant of the `b1` suffix — but the binary's version resource is now implicit behavior of the Inno version. **Fix:** pass an explicit numeric quad (`/DAppNumericVersion=0.9.0.0` → `VersionInfoVersion={#AppNumericVersion}`) derived in `build_installer.py`, so the file properties are deterministic and test-pinnable. Related, no finding: the `AppId={{7E6F…-KimCadBeta01}` non-GUID suffix is valid — AppId is a free-form string, `{{` escapes the literal brace, and the real compile/install/uninstall cycle proved the registry key round-trips.

## FINDING-007 (Nit) — the WebView2-missing friendly error doesn't name the .NET dependency

The shell stack is pywebview → pythonnet → clr_loader, which needs .NET Framework 4.7.2+. On the stated target (Windows 11) both .NET Framework 4.8 and the WebView2 runtime are **in-box**, so a clean Win11 box is fine — the live-window proof on this (dev-tooled) box generalizes. The risk is older Win10 images, where the shell's broad `except Exception` (SHELL-003) would catch the clr failure but the message names only WebView2. **Fix:** extend the friendly message to mention .NET Framework 4.7.2+/Windows 10 1803+ or state the Win11 floor in the docs — one string edit.

---

## What was checked and is sound

- **`[Run]` postinstall env**: the entry launches `pythonw + kimcad_launcher.py` with no env block — correct, because the launcher sets `KIMCAD_INSTALL_ROOT` in-process at module level (lines 23–25) before any kimcad import, and the AST test (`test_launcher_sets_the_seam_before_any_kimcad_import`) pins that order structurally. Shortcut, desktop icon, and postinstall all route through the same contract.
- **Download integrity**: embeddable Python over HTTPS with pinned SHA-256 verified before extraction; cache re-verified by hash on reuse; Inno compiler path pinned with its own recorded SHA.
- **Single-source version**: `#ifndef`/`#error` guards force the `/D` defines; `OutputBaseFilename=KimCad-Setup-{#AppVersion}` matches the build script's expected `KimCad-Setup-{version}.exe` exactly (PEP 440 `0.9.0b1` is filename-safe).
- **Staging smoke** gates the Inno compile under the *embedded* interpreter with the right env hygiene (`PYTHONDONTWRITEBYTECODE=1` for the smoke itself).
- **Uninstall data handling**: `%LOCALAPPDATA%\KimCad` removal is opt-in via MsgBox; `~/.kimcad` never touched; the final wizard page states the 13 GB model download plainly.

## Escalation verdict

**No escalation to audit-team.** Zero Blockers/Criticals; the one Major is release hygiene (dev tooling + ~36 MB riding in the payload), fully fixable inside this slice with a rebuild + re-run of the proven verify cycle. Per the 0/0/0/0/0 standard: fix FINDING-001 through 007, rebuild the installer, re-run `verify_install` (with the strengthened snapshot check) and the silent uninstall before calling 11.5 done.
