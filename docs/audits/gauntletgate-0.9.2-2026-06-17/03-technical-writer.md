# GauntletGate Full — Technical Writer — KimCad 0.9.2

**Role:** Technical Writer
**Auditor:** Claude Sonnet 4.6
**Date:** 2026-06-17
**Severity roll-up:** Blocker 0 · Critical 0 · Major 2 · Minor 1 · Nit 1

---

## Findings

### TW-001 — Major — Model storage location stale in three docs

**Severity:** Major

**Evidence:**

The 0.9.2 CHANGELOG entry (line 15–16) correctly documents the Minor-2 fix:

> "The managed Ollama process's `OLLAMA_MODELS` env var is now pinned to
> `%LOCALAPPDATA%\KimCad\models`, so the ~7.7 GB of downloaded models are covered
> by the uninstaller's existing `%LOCALAPPDATA%\KimCad` cleanup prompt — no more
> invisible 7+ GB orphan after uninstall."

But three user-facing documents continue to describe the old behavior — the models going
to "Ollama's standard model store" (i.e., `~\.ollama\models`), not the new KimCad-owned
path:

- `README.md` line 35:
  > "The engine lives under your per-user data folder (`%LOCALAPPDATA%\KimCad\ollama`)
  > and the models go in **Ollama's standard model store**; both are removable with the app data."

- `docs/install-guide.md` lines 61–63:
  > "The engine lives under your per-user data folder (`%LOCALAPPDATA%\KimCad\ollama`)
  > and the **models go in Ollama's standard model store**; both are removable with the app data."

- `docs/troubleshooting.md` line 98–99:
  > "(`%LOCALAPPDATA%\KimCad\ollama` for the engine, **Ollama's standard model store for
  > the models**) — never Program Files, and removable with the app data."

**Why it matters:** The primary user benefit of Minor-2 is that models are now under the
same `%LOCALAPPDATA%\KimCad` tree that the uninstaller already offers to clean up.
A user who reads the install guide or README before installing 0.9.2 will believe the
models still land in `~\.ollama` (Ollama's global store). If they try to reclaim the 7.7 GB
after uninstalling, they will look in the wrong place. The troubleshooting page compounds
this: a user following "where is my stuff?" will be sent to the wrong directory. This directly
contradicts the fix's stated purpose.

**Fix path:** In all three files, replace "the models go in Ollama's standard model store"
(and the troubleshooting variant) with:
> "the models are stored under `%LOCALAPPDATA%\KimCad\models` (KimCad's own data folder) —
> both the engine and the models are removed when you remove KimCad's app data."

The install-guide's "What the installer puts where" bullet should explicitly name
`%LOCALAPPDATA%\KimCad\models` alongside `%LOCALAPPDATA%\KimCad\ollama` for the engine.

---

### TW-002 — Major — USER-MANUAL.md version banner still says 0.9.1

**Severity:** Major

**Evidence:**

`docs/USER-MANUAL.md` line 15:
> `> **Version:** this manual tracks the current Windows beta (`0.9.1`). KimCad's version
> shows in **Settings → About** and from `kimcad --version`.`

The README badge (line 7) correctly reads `0.9.2`. The CHANGELOG leads with `[0.9.2]`.
The install guide checksum example command (line 16) correctly names `KimCad-Setup-0.9.2.exe`.
The USER-MANUAL version banner was not updated.

**Why it matters:** The USER-MANUAL is the primary reference for everyday users; it is
linked from the README as "the complete guide." A user who opens it and reads "this manual
tracks 0.9.1" has no way to know the behavior they're reading about applies to 0.9.2. For
the two behavioral changes in 0.9.2 (engine-down message wording, model storage path), this
creates a specific ambiguity: the manual is silent on both, and the stale version tag gives
no signal that it is behind. Any user who looks at the manual to understand engine-down
recovery will be reading 0.9.1-era guidance.

**Fix path:** Update line 15 of `docs/USER-MANUAL.md`:
```
> **Version:** this manual tracks the current Windows beta (`0.9.2`). ...
```

---

### TW-003 — Minor — CHANGELOG engine-down description inconsistent with actual message wording

**Severity:** Minor

**Evidence:**

The 0.9.2 CHANGELOG entry (lines 9–12) describes the fix as:
> "the chat now says **'the engine isn't running — restart from Settings'**"

The actual `MODEL_UNAVAILABLE_MESSAGE` in `src/kimcad/pipeline.py` lines 202–205 reads:
> `"KimCad couldn't reach your local AI — the engine isn't running. You can restart it
> from Settings, then try again."`

The CHANGELOG paraphrases correctly in spirit but quotes an inaccurate fragment. The real
message says "KimCad couldn't reach your local AI — the engine isn't running. You can
restart it from Settings, then try again." The changelog quote omits "KimCad couldn't reach
your local AI" and uses "restart from Settings" where the actual message says "restart it
from Settings, then try again."

**Why it matters:** Minor — the behavioral intent is accurately conveyed. However, a user
who copies the CHANGELOG quote when reporting a bug or writing a help article will be
quoting text that doesn't appear anywhere in the product. The inaccuracy makes it harder to
verify that the fix landed, and is inconsistent with the project's standard of exact quoted
evidence in changelogs.

**Fix path:** Update the CHANGELOG quote to match the literal message:
> "the chat now shows: *'KimCad couldn't reach your local AI — the engine isn't running.
> You can restart it from Settings, then try again.'*"

---

### TW-004 — Nit — ARCHITECTURE.md and docs/USER-MANUAL.md Part 3 silent on `OLLAMA_MODELS` pin

**Severity:** Nit

**Evidence:**

`ARCHITECTURE.md`'s module map entry for `pipeline.py` (line 92) and the Local-first section
(lines 285–298) discuss the managed Ollama integration at a high level but make no mention of
the `OLLAMA_MODELS` environment variable being set in `_child_env()`. The `ollama_runtime`
module is not listed in the module map at all, despite being the home of `_child_env()` and
the managed-engine logic. `USER-MANUAL.md` Part 3 (Architecture, lines 459–565) also omits
it.

**Why it matters:** The `OLLAMA_MODELS` pin is architecturally significant: it is the
mechanism by which KimCad scopes the model store to its own data directory, enabling the
uninstaller to clean up ~7.7 GB that would otherwise be invisible. A developer reading the
architecture to understand the managed-engine path will not find this. Nit because this is a
developer-facing gap, not a user-facing inaccuracy.

**Fix path:** Add `ollama_runtime.py` to ARCHITECTURE.md's module map with a one-line
description, e.g.:
> `ollama_runtime.py` — managed headless Ollama lifecycle: locate/reuse system Ollama or
> download the portable build; `_child_env()` pins `OLLAMA_MODELS` to the KimCad data dir
> so models are stored under `%LOCALAPPDATA%\KimCad\models` and covered by the uninstaller.

---

## What's working (specific and credited)

**CHANGELOG.md — 0.9.2 section is accurate, user-oriented, and complete on behavior.** Both
fixes are described in terms of the user's experience (what message they saw, what goes
wrong on uninstall) rather than in terms of code. The tester-007 issue references are
preserved for traceability. The Minor-2 fix correctly names both the old location (`~/.ollama`)
and the new (`%LOCALAPPDATA%\KimCad\models`) and explains exactly why it matters to the user
(no invisible 7+ GB orphan). The quantification ("~7.7 GB", "7+ GB") is consistent.

**README.md — version badge updated correctly.** The `![beta](https://img.shields.io/badge/beta-0.9.2-2563eb)` badge on line 7 was updated and matches the released version.

**docs/install-guide.md — installer filename is correct.** Line 16 shows `KimCad-Setup-0.9.2.exe` in the checksum verification command, consistent with the version bump.

**docs/api.md — `model_unavailable` status is correctly documented and consistent with the code.** The API docs (lines 57–60) list `model_unavailable` as a `status` value with the description "(the local AI isn't running — recoverable)" — the description no longer mentions "Ollama" and aligns with the new user-facing language.

**docs/troubleshooting.md — engine-down heading aligned with new message.** Line 7 reads "KimCad couldn't reach your local AI" which matches the updated `MODEL_UNAVAILABLE_MESSAGE` wording. This heading was correctly updated.

**No stale "Make sure Ollama is running" in user-facing docs.** A search of the entire `docs/` tree finds that phrase only in historical audit records (stage-a, stage-9) — it does not appear in any user-facing document (README, USER-MANUAL, FAQ, install-guide, troubleshooting, api.md). The old message has been cleanly retired from user-visible documentation.

**CHANGELOG historical entries are preserved intact.** The 0.9.1 and earlier entries were not modified, and the 0.9.2 entry sits correctly above them.

---

## Coverage gaps

**The `OLLAMA_MODELS` behavior in `docs/USER-MANUAL.md` Part 1 (everyday user section).** The
"When something goes wrong" table (lines 258–270) and the "What the installer puts on your
machine" section in README say models go to "Ollama's standard model store." The everyday
user who reads Part 1 of the manual to understand where their files are will get the pre-0.9.2
answer. The manual's Part 3 (Architecture) also makes no mention of this.

**`docs/FAQ.md` — Q4 and Q7 not updated.** FAQ Q4 (line 34–41) says "if Ollama is already
installed it just uses it, otherwise it downloads Ollama's official portable build into its
own data folder" — this is still accurate, but makes no mention of where models go (previously
`~/.ollama`, now `%LOCALAPPDATA%\KimCad\models`). FAQ Q7 (line 57–60) says "Saved designs,
settings, and the learning history live in `~/.kimcad`" — again, accurate but it omits the
model store location. These are gaps rather than inaccuracies; no finding is raised because
the FAQ's stated scope is "quick answers" and it never directly claimed models land in any
specific place. However, a revision to FAQ Q4 that names the new storage path would close the
coverage gap for everyday users.
