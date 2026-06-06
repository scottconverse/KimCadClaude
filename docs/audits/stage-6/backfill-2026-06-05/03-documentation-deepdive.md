# Stage 6 (model layer + bake-off) — Documentation deep-dive

**Role:** Senior Technical Writer (independent, skeptical)
**Scope:** Docs accuracy for the model layer — README (model/local-first + LLM backend
sections), ROADMAP Stage 6, CHANGELOG Stage 6 entries, `docs/benchmarks/stage-6-model-bakeoff.md`,
`config/default.yaml` (backends/model config), ARCHITECTURE (provider/advisor). Cross-checked
against `src/kimcad/model_advisor.py`, `llm_provider.py`, `bakeoff.py`, `benchmark.py`, `cli.py`.
**Date:** 2026-06-05 · **Branch:** `stage-0-7-audit-backfill`
**Mode:** AUDIT-ONLY (findings recorded; no drafts written)

> Note on the gemma4-only stance: per the hard project rule, `gemma4:e4b` is THE model and the
> bake-off verdict (keep gemma; Qwen rejected) is the intended, correct conclusion. Nothing below
> flags that stance. Findings concern only drift, overclaim, stale status, links, and statements
> a reader could be misled by.

---

## What's working (credit where due)

The model-layer docs are, on the whole, unusually honest and accurate — this is a strong set.

- **The bake-off doc is excellent.** `docs/benchmarks/stage-6-model-bakeoff.md` states the verdict
  up front, shows the actual result table, explains *why* Qwen failed (echoes the schema; a
  code-completion model is the wrong tool for NL→structured-plan), pre-empts the "use a bigger Qwen"
  objection with the speed argument, gives reproduction steps, and documents the recommend-only rule.
  Every number in its table is internally consistent with the grading code: gemma `completed 8/10`,
  `graded 4/10`, `dims 5/9` reconciles exactly with `Outcome.graded_passed` (benchmark.py:63 — completed
  AND no *assessed* axis False; 8 completed − 4 dim-failures = 4 graded). The "qwen shows n/a, not 0/0"
  treatment matches `Bakeoff.to_text` (bakeoff.py:168-171). This is a model of an honest benchmark write-up.
- **The recommend-only / human-call framing is consistent everywhere** — README:275, bake-off
  doc "recommendation rule" + "making a switch", ROADMAP:182-183, CHANGELOG:100-101, ARCHITECTURE:98,
  and the code (`compare_runs`, bakeoff.py:53-129; cli.py never writes config). No doc overclaims that
  the harness flips the default.
- **The advisor's "advisory only, never rewrites config" claim is true and repeated faithfully**
  (README:118-120, ARCHITECTURE:97, model_advisor.py docstring + pure `recommend`). The non-China-escape
  requirement is documented (README:120 indirectly; CHANGELOG:93-95) and really implemented
  (`_non_china_escape`, model_advisor.py:305-317).
- **`config/default.yaml` comments are accurate and load-bearing** — the `local_qwen` block (lines
  57-64) documents the 0/10 rejection inline; the `local` block explains the gemma sizing rationale.
- **All cross-doc links in scope resolve.** `docs/benchmarks/stage-5-template-families.md`,
  `docs/benchmarks/stage-6-model-bakeoff.md`, `docs/printproof3d-integration.md`, and the
  `config/default.yaml` reference all exist on disk (verified).
- **CLI claims verified:** `kimcad models` probes RAM/CPU/GPU (README:118 ↔ `probe_hardware`);
  `kimcad bakeoff --backends` defaults to `local_qwen,local` and slices by default (README:271-275 +
  bake-off doc ↔ cli.py:132, :140-145); `plan_failed` clean-fail (CHANGELOG:102-103 ↔ `PlanParseError`,
  llm_provider.py:50-57). The `kimcad bench --min-success-rate 0.8` done-gate (README:264-269) matches
  `Summary.meets` (benchmark.py:218).

---

## Findings

### DOC-001 — Major — Accuracy — README undersells the cloud backends it ships (OpenRouter omitted from the prose)
**Evidence:** README:66-69 and 113-116 describe the optional cloud fallback as "DeepSeek **or any
OpenAI-compatible endpoint**." But the model layer's real, user-facing cloud story is **OpenRouter** —
`config/default.yaml` ships a named `custom_openrouter` backend (lines 70-77), the model_advisor surfaces
cloud, and the *entire Stage 8.5 cloud opt-in UX* is built on OpenRouter (CHANGELOG:65-71 "an
off-by-default cloud opt-in via **OpenRouter**"; ROADMAP repeatedly pairs "DeepSeek/OpenRouter").
The README's setup section (line 116) does name `custom_openrouter`, but the two prose sentences a
first-time user actually reads (lines 68, 114) say only "DeepSeek / any OpenAI-compatible endpoint."
A reader scanning the LLM-backend section would not learn that OpenRouter is the blessed, in-app
cloud path.
**Why it matters:** The first-time user evaluating "can I use cloud?" gets an accurate-but-vague
answer that buries the one cloud provider KimCad actually wired an in-app key field and Settings
toggle for. DeepSeek, by contrast, is config-only (no Settings UI). The prose inverts the prominence
of the two.
**Blast radius:**
- Adjacent docs: ARCHITECTURE:203-206 has the same "DeepSeek or any OpenAI-compatible endpoint"
  phrasing and the same omission; fix both together.
- Shared state: none (doc-only).
- User-facing: affects how users discover the cloud opt-in; no code change.
- Tests: none.
- Related findings: DOC-002 (the broader DeepSeek-vs-OpenRouter prominence question).
**Fix path:** In README:68 and 114 (and ARCHITECTURE:204), name OpenRouter alongside DeepSeek —
e.g. "a cloud API (OpenRouter, DeepSeek, or any OpenAI-compatible endpoint), opt-in via the in-app
Settings screen (OpenRouter) or `config/local.yaml`." Short edit; no draft needed.

### DOC-002 — Minor — Accuracy — `cloud_deepseek` `model_name` is a VERIFY-marked, likely-nonexistent tag presented without a caveat in user-facing context
**Evidence:** `config/default.yaml`:39 sets `cloud_deepseek.model_name: deepseek-v4-flash` with an
inline `# VERIFY §7.1 — exact tag + pricing move weekly`. The model_advisor catalog (model_advisor.py:121)
and README:116 point users at `cloud_deepseek` as a ready-to-use backend. "deepseek-v4-flash" is not a
known DeepSeek model id (DeepSeek's line is deepseek-chat / deepseek-reasoner); the VERIFY marker is an
honest flag *in the config*, but a user who copies `cloud_deepseek` per the README would hit a
model-not-found at runtime with no doc warning.
**Why it matters:** A returning user opting into the documented cloud fallback could get a confusing
404. The config comment carries the caveat; the README that *sends* them there does not.
**Blast radius:** doc + config only; no code path asserts this tag. Tests: none.
**Fix path:** Either (a) update the tag to a real current DeepSeek id, or (b) add one clause to
README:116 noting the cloud `model_name` values are placeholders to verify against the provider's
current catalog. (b) is lower-risk and matches the project's VERIFY convention.

### DOC-003 — Minor — Completeness — ROADMAP/CHANGELOG say Qwen was ruled out but don't name the larger-Qwen catalog entries the advisor still carries
**Evidence:** ROADMAP:179-183 and CHANGELOG:104-106 say the `Qwen2.5-Coder 1.5B` candidate was
evaluated and rejected, and explain a *bigger* Qwen would be slower (correct reasoning). But the
advisor catalog actually ships **three** Qwen entries — `1.5b`, `3b`, `7b` (model_advisor.py:109-117),
each marked "REJECTED candidate; deprioritized." A reader reconciling the docs ("we tested 1.5B") with
`kimcad models` output (which can list 3B/7B as deprioritized alternatives) finds entries the docs
never mention. Note the 3B/7B were *not* bake-off-tested — only reasoned about — yet their catalog
`notes` say "REJECTED candidate," which slightly overstates the evidence (1.5B was empirically
rejected 0/10; 3B/7B were deprioritized by argument, not measured).
**Why it matters:** Minor reader-confusion / a small evidence-altitude slip (reasoned-out vs
measured presented identically). Not user-blocking.
**Blast radius:** ARCHITECTURE:97 ("surfaces a non-China alternative") is consistent; no other doc.
Tests: advisor unit tests may assert catalog shape — check before re-wording notes. Migration: none.
**Fix path:** One line in the bake-off doc or ROADMAP noting the catalog also carries deprioritized
larger-Qwen entries for completeness, and (optional) soften the 3B/7B catalog `notes` from "REJECTED"
to "deprioritized below gemma4 (larger → slower on CPU; not separately bench-tested)" so the
empirically-rejected 1.5B and the reasoned-out siblings read distinctly.

### DOC-004 — Minor — Accuracy — Bake-off doc's stated runtime ("gemma ~10 min/prompt") diverges from the recorded result table (~9.9 min mean)
**Evidence:** `stage-6-model-bakeoff.md` line 67 says "gemma is ~10 min/prompt"; the result table on
line 14 records `mean_s 595.7` (≈9.93 min). These agree (rounding), so this is genuinely a Nit-level
rounding note rather than a contradiction — flagged Minor only because the README/ROADMAP elsewhere
lean on the "fast on the target box" framing and a casual reader pairing "~10 min/prompt" with "fast"
may be surprised. The doc is honest (it says "tens of minutes to an hour-plus" for a full run); the
"fast + stable" adjective in README:107 / config:50 is relative to gemma3:12b, not absolute.
**Why it matters:** Very low. Only a reader conflating "fast default" (vs the 12b that crashed) with
"fast wall-clock" could be momentarily misled. The docs do not actually claim low latency.
**Blast radius:** README:106-107, config/default.yaml:50-51 ("fast + stable there"). No code.
**Fix path:** Optional. If desired, qualify "fast" once as "fast *and stable relative to gemma3:12b*"
where it first appears (README:107). Otherwise leave — the bake-off doc already states the real numbers.

### DOC-005 — Nit — Tone/Consistency — "the model layer" status is stated correctly as DONE/tagged across docs; one stale-risk phrasing to watch
**Evidence:** Stage 6 is consistently reported DONE + tagged `stage-6` (README:23-24, ROADMAP:162/184-185,
CHANGELOG:9-12/92). No stale "pending/next" status for Stage 6 was found — this is correct and a
contrast with the Stage-4 lesson the docs cite. The only forward-looking phrasing is ROADMAP:179-183's
"(Bigger benchmark prompt set is deferred to a later stage)" which is accurate. No fix required;
recorded so the verdict reflects that stage-status accuracy was checked and passed.
**Fix path:** None.

---

## Severity rollup (this role)

```
Blocker:  0
Critical: 0
Major:    1   (DOC-001)
Minor:    3   (DOC-002, DOC-003, DOC-004)
Nit:      1   (DOC-005)
-----
Total:    5
```

## Verdict

**PASS with one Major.** The Stage-6 model-layer documentation is accurate, honest, and well
cross-referenced — the bake-off write-up in particular is a standout, and every load-bearing claim
about the advisor, the fallback, the bake-off verdict, the recommend-only rule, and the gemma4-only
stance checks out against the code. No statement is contradicted by the implementation; no link is
broken; Stage-6 status is correctly reported as DONE/tagged. The single Major (DOC-001) is a
prominence/omission issue, not a falsehood: the README's prose names DeepSeek and "any OpenAI-compatible
endpoint" but omits OpenRouter, which is in fact the blessed in-app cloud path the product built UX
around. The three Minors are a placeholder DeepSeek tag without a user-facing caveat, an unmentioned
pair of deprioritized Qwen catalog entries (with a small reasoned-vs-measured evidence slip), and a
"fast"-adjective nuance. None block a release; DOC-001 should land before beta-facing docs are
finalized.

**Report path:** `C:\Users\scott\dev\kimcad\docs\audits\stage-6\backfill-2026-06-05\03-documentation-deepdive.md`
