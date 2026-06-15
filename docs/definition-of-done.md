# Definition of done

What "done" means in KimCad, made explicit — for contributors, and for anyone auditing a
claim. This is the discipline every shipped stage actually went through (the evidence trail
is committed under `docs/audits/`).

## Per-change (every slice, before it merges)

1. **Scope is thought through before code** — the approach and blast radius are clear up front,
   with a written plan when the change warrants one (historically under `.claude/plans/`). This is
   a planning discipline, not a hard per-slice gate.
2. **Tests land with the behavior.** A change that touches logic, data flow, or a public
   interface carries a test that would fail without it — written against the project's
   existing frameworks (pytest / vitest). Never weaken an existing test to get green.
3. **The authoritative gate passes** — one script, `scripts/ci.sh`, run identically by the
   pre-push hook and by CI:
   - `ruff` clean;
   - geometry-backend preflight (a degraded trimesh stack fails fast, not as 30 misleading
     test errors);
   - **binary advisory review** (`scripts/check_binary_advisories.py`) — a pinned
     OpenSCAD/OrcaSlicer bump without a reviewed CVE assessment fails the gate;
   - the **full pytest suite**, including the live OrcaSlicer slice and the live CadQuery
     worker tests on the provisioned box (strict mode fails on ANY skip there — green by
     skip is not green);
   - **vitest** (the full SPA unit suite) + **build reproducibility** (the committed SPA
     must byte-match a fresh build);
   - CI additionally runs **pip-audit** against `requirements.lock` and the
     **installer-staging smoke** (`build_installer --stage-only` + `verify_install` on the
     staged tree).
4. **Honest states, not just happy paths.** A user-reachable failure (model down, tool
   missing, stale design, refused send) is a typed, actionable status — never a 500, never
   success-shaped copy.
5. **Docs move with the code.** A change to user-facing behavior updates the affected docs
   (README / USER-MANUAL / guides / CHANGELOG) in the same commit.

## Per-stage (before a stage tag)

6. **A runtime walkthrough** — the product driven as a user in a real browser (not a unit
   suite): every new journey end to end, against real models/tools where the claim depends
   on them, with evidence captured under `docs/audits/`.
7. **A five-role audit** (engineering / UI-UX / docs / test / QA) of the stage diff, and
   **every finding remediated to 0/0/0/0/0** — zero open Blockers, Criticals, Majors,
   Minors, *and* Nits — then independently re-audited. No cleanup lists carried forward.
8. **Claims are measured, not asserted.** A performance or quality claim (model choice,
   pass-rate lift, build-volume numbers) carries a committed, re-runnable measurement —
   and gets re-measured rather than trusted when the underlying model/tool changes.

## The beta bar (what the beta actually means)

- Double-click Windows installer; the **installed tree** verified by
  `scripts/verify_install.py` (not just the dev checkout); release artifacts carry
  SHA-256 attestation + a manifest with the exact source commit.
- The full pipeline proven in CI for the reference printers: prompt → plan → deterministic
  template (or gated experimental) → render → mesh validation → Printability Gate →
  auto-orient → harden → **real OrcaSlicer slice**.
- Direct print behind explicit confirmation, gate-failed parts unsendable server-side,
  no auto-start anywhere, secrets in the OS credential store, loopback-only serving.
- **Honesty boundary:** printer protocols are conformance-validated, not metal-validated —
  no physical print is certified; that is the beta's own job, and the docs say so
  everywhere the claim could be misread.

## Explicitly not done by closing an issue

Real-hardware validation (needs printers), code signing (needs a certificate), and
macOS/Linux installers are tracked openly on the issue board rather than silently dropped —
an issue closes only with a verified fix or a documented, deliberate won't-fix.
