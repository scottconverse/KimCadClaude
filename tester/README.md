# KimCad clean-machine test channel (`tester` branch)

> ## ▶ CURRENT DIRECTIVE: [`directive-002-clean-install-evidence-first.md`](directive-002-clean-install-evidence-first.md)
> Read it and run it. Two non-negotiable rules: **(1) every claim needs a committed artifact under
> `evidence/002/` — no narration; (2) prove you're on the CORRECTED build (Phase 3 gate) before testing
> anything — the public Releases build is STALE.** `directive-001` is superseded; ignore it.

This branch is an **async coordination channel** between two Claude agents over git:

- **DEV** — Claude on the build box (writes test directives, reads reports, decides follow-ups).
- **TESTER** — Claude (cowork) on the clean test machine `DESKTOP-2BR3SJR` (AMD Ryzen 7 8745HS /
  Radeon 780M / 32 GB / fresh Windows 11). Runs the directives on real hardware, writes reports.

The git history **is** the conversation. Neither side needs the other online at the same time.

## How it works

1. **DEV** writes `directive-NNN-<slug>.md` — a test plan carrying a unique **NONCE**.
2. **TESTER** reads the newest directive, runs it on the clean machine, and writes
   `reports/report-NNN-<slug>.md` — **echoing the directive's NONCE** so DEV knows which directive
   the report answers. Screenshots / logs / hashes go under `evidence/NNN/`.
3. **DEV** reads the report and either signs off or writes `directive-(NNN+1)-*.md` with follow-ups.
4. Repeat until DEV writes a directive whose only content is **`SIGN-OFF`**.

## Cadence — the 10-minute heartbeat

Both sides `git pull origin tester` every ~10 minutes and act on anything new from the other side.
Every heartbeat, **append one timestamped line to `STATUS.md`** (newest at the bottom) saying what
you're doing — this is the liveness signal. A side that goes quiet for >30 min without a STATUS line
is treated as stalled.

## Ownership (so pushes don't collide)

- **DEV owns** `directive-*.md` and `SIGN-OFF`.
- **TESTER owns** everything under `reports/` and `evidence/`.
- **`STATUS.md` is append-only** by both — on a conflict, keep BOTH sides' lines (never overwrite).
- Always `git pull --no-rebase` before you push. **Never force-push.**

## Push rules

- **TESTER:** do **not** run `git config core.hooksPath .githooks` on your clone — that would arm
  the build box's heavy pre-push gate. Your pushes to this branch should be plain and instant.
- **DEV:** the branch-aware pre-push hook (committed 2026-06-15) skips the full gate for any
  non-`main`/non-tag ref, so pushes to `tester` are instant. The gate still fires for `main`.
- This branch is a **scratch coordination channel** — it is never merged into `main`.
