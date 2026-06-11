# Stage 11 dispositions (recorded for the beta gate)

1. **PrintProof3D bundling — DONE (the ROADMAP's gated branch resolved in favor).**
   Verified 2026-06-10: the engine reached **stable v0.5.0** (released 2026-06-03, real
   Windows binaries on the GitHub release). Bundled into the installer pinned by URL +
   SHA-256 (`scripts/build_installer.py`, `tools/printproof3d/printproof3d.exe` — the
   path `config/default.yaml` has named since Stage 7), so a default install gets the
   real overhang/bridge/bed-adhesion validation. The Stage-7 wrapper's graceful
   degradation (absent/misbehaving engine → gate-only, honestly labeled) is unchanged
   and remains the safety net.

2. **CadQuery worker OS-level confinement (the Stage-8 accepted deferral) —
   RE-ACCEPTED, with a STRONGER rationale than at Stage 8.** The beta installer ships
   **without** the CadQuery backend entirely (no worker venv in the payload; the app's
   Stage-8 graceful-absence posture covers it: OpenSCAD carries every template family
   and the experimental path, and STEP export is simply not offered). Therefore the
   confinement question does not exist in the artifact beta users run. It applies only
   to from-source users who deliberately create `.venv-cq313` — who get the documented
   Stage-8 security model (ast sanitizer + geometry-only facade + restricted builtins +
   env/cwd isolation + the release-gate canary). OS-level confinement (job objects /
   restricted tokens, requiring pywin32) stays on the post-beta list, prioritized if the
   backend ever ships in the installer.

3. **Hosted CI — NOT re-enabled (owner decision, Scott, 2026-06-10), superseding
   ROADMAP's "re-enable hosted CI" line.** The repo is private and hosted minutes are
   limited; the self-hosted runner (this box, strict zero-skip gate, live OpenSCAD/
   OrcaSlicer/CadQuery tests hosted runners couldn't run anyway) is the release gate.
   Revisit only if the project goes public or gains contributors without runner access.

4. **Per-user install tradeoff — DISCLOSED.** A no-admin install lands in a
   user-writable directory (the VS Code tradeoff). `docs/install-guide.md` states it and
   recommends Program Files when unsure; the installer defaults to Program Files.
