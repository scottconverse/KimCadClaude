# Audit Lite — Stage 7 Slice 2: PrintProof3D arm's-length wrapper
**Date:** 2026-06-02
**Scope:** `src/kimcad/printproof3d.py` (`validate_model`, `_subprocess_runner`, `_parse_report`, `printer_profile`/`material_profile`), the optional `binaries.printproof3d` in `config/default.yaml` + `Config.printproof3d_binary()`, and `tests/test_printproof3d.py` (13 cases).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after one Minor. The wrapper is exactly the right shape: arm's-length subprocess (argv list, no shell, no linkage), gated on the parsed report file rather than the exit code, with profile generation that the **real engine accepted in a live run**. Every intended degrade path returns `None`. The one hole: `_parse_report` iterates `issues`/`suggested_fixes` without guarding them to lists, so a malformed-but-parseable report (`"issues": 5`) raises `TypeError` out of a function whose whole contract is "never raises" — confirmed live.

## Severity rollup

> **FINAL (after remediation): 0 / 0 / 0 / 0 / 0 — the 1 finding is fixed.** See "Re-audit (resolution)" below; verified by `tests/test_printproof3d.py`.

**As found:** 0 Blocker · 0 Critical · 0 Major · 1 Minor · 0 Nit.

## Findings

### PP-001 Minor: `_parse_report` can raise on a malformed (non-list) `issues`/`suggested_fixes`, breaking the never-raises contract
**Dimension:** Correctness
**Evidence:** `printproof3d.py:115` does `for raw in data.get("issues", []) or []` and `:121` `fixes = raw.get("suggested_fixes") or []`. If the report is a valid-JSON dict but `issues` (or a `suggested_fixes`) is a truthy non-iterable, the `or []` keeps the bad value and the `for` loop raises. Confirmed live: `_parse_report({"status":"pass","issues":5})` and a report with `"suggested_fixes": 7` both raise `TypeError: 'int' object is not iterable`. Because `validate_model` calls `_parse_report(data)` outside a try (`:103`), that `TypeError` escapes `validate_model` — which is documented and tested as "never raises."
**Why it matters:** The wrapper's reason for existing is to be a safe boundary to an external, in-development engine: a flaky/garbled engine response must degrade to `None`, never crash the pipeline. The real engine won't emit `issues: 5`, but a truncated/corrupted report that still parses as a dict can, and this is exactly the case the wrapper promises to absorb. A single edge that raises defeats the contract.
**Fix path:** Coerce both to lists before iterating: `issues_raw = data.get("issues"); issues_raw = issues_raw if isinstance(issues_raw, list) else []` and `fixes = raw.get("suggested_fixes"); fixes = fixes if isinstance(fixes, list) else []`. Add a test: `_parse_report({"status":"pass","issues":5})` returns a `PrintProofReport` with no issues (not a raise), and a report whose issue has a non-list `suggested_fixes` parses with empty fixes.

## What's working
- **Arm's-length and injection-safe.** PrintProof3D is only ever a subprocess (`_subprocess_runner` → `subprocess.run(argv, …)`, an argv list, `check=False`, no shell); the module never imports or links the engine. The binary path comes from config or an explicit arg, not user input on a hot path. This matches the spec's "invoked at arm's length, never linked into the KimCad process."
- **Gated on the report, not the exit code.** The return code is deliberately ignored (PrintProof3D exits non-zero on a fail *verdict* — a normal result); `validate_model` reads the `-o` report file and only that determines success. The `except Exception` around the run is correctly scoped: it catches a timeout/OSError but then *falls through to read the report*, so even a partially-failed run that wrote a report still parses. The `# noqa: BLE001` is justified for an external-process boundary.
- **Graceful degrade is thorough.** `binary=None`, a profile-write error (`OSError/TypeError/ValueError`), a runner that raises, no report file, a non-JSON report, a non-dict body, and a bad `status` each return `None` — six distinct degrade paths, all tested. Smart Mesh keeps working on KimCad's own gate when the engine is absent.
- **Profile generation is live-validated.** `printer_profile`/`material_profile` build minimal-but-valid PrintProof3D profiles (all 23 + 13 required schema fields; `RiskLevel`s exactly low/medium/high; `build_volume {type:rectangular,x,y,z}`; thermal window around KimCad's temps). The live run against the real binary returned a parsed report, which *proves* the engine accepted the generated profiles — the most important correctness check for this slice, and it passed.
- **Honest config seam.** `Config.printproof3d_binary()` returns `None` when the key is unset *or* the file isn't on disk (so a configured-but-not-yet-fetched path degrades rather than crashes), resolves relative to the project root, and never raises — tested both ways.
- **The bed-positioning gotcha is documented where it belongs.** The live smoke surfaced that PrintProof3D measures extents from the bed origin `[0, build]`, so a centered-on-origin part false-flags `MODEL_OUT_OF_BOUNDS`; `validate_model`'s docstring names bed-positioning as the Slice-3 caller's job. Correctly scoped, not papered over.

## Watch items
- **`printer_profile` `bv[2]` assumes a 3-tuple.** `bv = printer.build_volume or (256,256,256)` then `float(bv[0..2])` — a hand-built `Printer` with a malformed 2-tuple `build_volume` would `IndexError` (not caught by the `OSError/TypeError/ValueError` around profile-gen). `config.py` guarantees `build_volume` is `None` or a 3-tuple, so it can't happen via config; noting only because the never-raises contract is otherwise airtight. If you want it bulletproof, fold the profile-gen into the same defensive coercion as PP-001.
- **Slice 3 must bed-position the oriented mesh** (translate min-corner to the origin) before calling `validate_model`, or every real part trips a false out-of-bounds. Already on the docstring; restating so it isn't lost between slices.

## Escalation recommendation
No escalation needed. One Minor never-raises hole in a new, well-scoped, live-verified wrapper. Fix PP-001 and re-audit to 0/0/0/0/0; the Stage-7 stage-end audit-team covers the branch.

---

## Re-audit (resolution) — 0/0/0/0/0

- **PP-001 (Minor) — FIXED.** `_parse_report` now coerces `issues` and each `suggested_fixes` to a list before iterating (`issues_raw if isinstance(issues_raw, list) else []`), so a malformed report parses with empty issues/fixes instead of raising. New test `test_parse_report_degrades_not_raises_on_a_non_list_issues_or_fixes` pins both cases (`issues: 5` → no issues; `suggested_fixes: 7` → empty fixes). The watch-item profile-gen path was also hardened — its catch now includes `IndexError/KeyError/AttributeError`, so a malformed `Printer`/`Material` degrades too. The never-raises contract is now airtight.

Verified: `tests/test_printproof3d.py` **14 passed**; ruff clean; `_parse_report` on `{"status":"pass","issues":5}` returns a report with no issues (no raise). **Roll-up: 0/0/0/0/0.**
