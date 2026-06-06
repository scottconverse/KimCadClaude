# Stage 7 — Engineering Deep-Dive (Principal Engineer)

**Audit:** KimCad Stage 7 backfill — Smart Mesh readiness + PrintProof3D + learning store
**Branch:** `stage-0-7-audit-backfill`
**Scope:** `src/kimcad/smart_mesh.py`, `src/kimcad/printproof3d.py`, `src/kimcad/history.py`, with `printability.py` / `pipeline.py` / `webapp.py` read for the gate-authority boundary.
**Reviewer stance:** Independent, skeptical. Audit-only — no code changed.
**Bar:** release-quality beta, zero findings.

---

## Verdict

**PASS — ship.** Stage 7 is well-architected and correct against its own stated contract. The load-bearing invariant — *the deterministic Printability Gate stays the slice authority; the readiness card is advisory and can never flip a gate-fail into a sliceable pass* — holds, and it holds at the right layer (the web slice/send endpoints gate on `gate_status_by_rid`, not on readiness; `webapp.py:1268`, `:1736`, `:1274`). PrintProof3D is genuinely arm's-length (subprocess, never linked), genuinely optional, and degrades cleanly to gate-only at honest, lower confidence. The learning store is local-first, bounded, atomic, thread-safe, never blocks the build, and leaks nothing identifying.

The findings below are all Minor/Nit. None block release. I went looking hard for a Major+ (an attribution that overstates, a score that contradicts the gate, a degrade path that 500s, a PII leak, a race) and did not find one. The defensive depth here is unusually good for a beta.

---

## What's working (specific, earned credit)

- **Worst-of-two-signals verdict (`smart_mesh.py:164–182`).** The card tone is `max(kc_tone, pp_tone)` over a severity rank, so the card is *never more optimistic than either* KimCad's own assessment or the PrintProof3D engine it cites. A PrintProof3D `status="fail"` whose worst individual issue is only `major` (penalty wouldn't sink the score below 50) still renders "Not print-ready" — verified by `test_printproof_fail_status_forces_not_ready_even_with_only_a_major_issue`. This is exactly the right conservatism for an advisory card and is the single best design decision in the stage.

- **Honest attribution + confidence (`smart_mesh.py:209–225`).** Confidence is `High` only when the deeper engine ran *and* the mesh was analysable; an unanalysable mesh forces `Low` even when PrintProof3D returned `High` (`test_unanalysable_mesh_keeps_confidence_low_even_when_the_engine_ran`). The attribution string names what actually backed the verdict ("KimCad printability gate" vs "PrintProof3D validation engine" vs "...mesh only partly analyzable"), and the history layer *augments* it ("...and your local build history") only when a comparison was actually produced (`pipeline.py:609–624`). The card never claims the engine ran when it didn't.

- **PrintProof3D never raises (`printproof3d.py:53–111`).** Every failure mode — no binary, profile-serialize failure, runner raise, no report written, unparseable report, malformed report body — returns `None` and degrades to gate-only. The runner deliberately ignores the subprocess exit code because a non-zero exit is how the engine signals a *fail verdict*, not a crash; the parsed report file is the source of truth. stdout/stderr are captured (not inherited) so the engine can't scribble on KimCad's console. This is a textbook arm's-length integration.

- **Defensive report parsing (`printproof3d.py:160–196`).** Non-dict body → `None`; bad `status` → `None`; non-list `issues` → empty; unknown severity → issue dropped (not guessed); non-list `suggested_fixes` → empty. `_sanitize_geometry` validates the engine's three location shapes, rejects bools-as-coordinates (`_num`, line 119 — `bool` excluded as an `int` subclass), and caps forwarded triangles at `_MAX_HL_TRIANGLES = 4000` so a pathological problem region can't bloat the browser payload. Untrusted-input discipline applied to a *local* engine's output is the correct paranoia.

- **History store is genuinely best-effort + safe (`history.py`).** Atomic write (temp + `os.replace`, line 132) under a process-wide lock (line 122) — the concurrency test drives 40 simultaneous writers and loses zero records. `allow_nan=False` rejects a non-finite `max_dim_mm` and the whole write is swallowed rather than corrupting the file. Load skips any malformed record without poisoning the rest. Bounded at `_MAX_RECORDS = 500`. The comparison wording is provably *factual not flattering*: "personal best" needs a strict beat of every prior, a tie reads "on par" (not "below"), and the same-type pool only narrows at `>= _MIN_SAME_TYPE` (the `==2` boundary still compares against all parts — `test_compare_phrase_at_two_same_type_still_falls_back_to_all_parts`).

- **No PII / no exfiltration.** `PrintRecord` (`history.py:39–50`) stores object_type, score, gate_status, material, largest-dimension, and an optional timestamp — explicitly "no geometry, no prompt, nothing identifying." The store path defaults to `~/.kimcad/history.json`, never the repo (`config.py:134–143`). PrintProof3D runs as a local subprocess; nothing leaves the machine.

- **Readiness is computed on the artifact that ships.** `_compute_readiness` runs on the *hardened* mesh (`pipeline.py:515–517`), bed-positions a `hardened.copy()` (line 591 — the original is not mutated) so PrintProof3D measures extents from `[0, build]` without a false `MODEL_OUT_OF_BOUNDS`, and `_fallback_readiness` (`pipeline.py:285–297`) guarantees a card even if the pure `assess_readiness` somehow raised. The never-breaks-the-build contract is airtight: two nested `try/except` layers around the engine and the synthesis.

- **Test coverage is real and adversarial.** `test_smart_mesh.py`, `test_printproof3d.py`, `test_history.py`, `test_pipeline_readiness.py` cover the happy path *and* every degrade path, purity (`test_assess_readiness_is_pure_same_inputs_same_output`), score clamping, dedupe, bed-positioning assertion, "engine runs once, not per drag," and "gate-failed part still gets a card and is still recorded." Tests carry finding IDs (SM-001, PP-001, ENG-701, SLICE5-001) tracing back to prior fixes — a mature regression discipline.

---

## Findings

### ENG-701 (Minor / Correctness) — A PrintProof3D `pass` status carrying a `minor` issue is silently dropped from the score-vs-verdict story

**Evidence:** `smart_mesh.py:35` `_PP_RISK_TONE = {"blocker":"fail","critical":"fail","major":"warn","minor":"warn"}` — `minor` surfaces as a `warn` risk. `smart_mesh.py:33` penalizes `minor` by 6. So an engine report `status="pass"` with one `minor` issue produces: score 92→86, a `warn` risk, and `kc_tone="warn"` (because `risks` is non-empty, line 172) → final verdict "Printable with notes" even though the engine's own overall status was `pass`. The card is *more* conservative than the engine here.

**Why this matters:** This is defensible conservatism (worst-of), and arguably correct — a real minor issue *should* nudge the card off a clean "Ready to print." But it is an *asymmetry worth a one-line doc note*: the module's docstring and the `_PP_RISK_TONE` comment say "minor → warn," yet there is no test asserting the pass-status + minor-issue combination, and a future reader could reasonably expect a `pass` engine status to keep "Ready to print." Today it doesn't. This is a documentation/test gap, not a bug.

**Fix path:** Add one test pinning the intended behavior (engine `pass` + single `minor` issue → "Printable with notes", score 86), and a one-line comment at `smart_mesh.py:170–175` noting that a surfaced `minor` risk intentionally drops a clean pass. No code change.

---

### ENG-702 (Minor / Correctness) — Unmapped PrintProof3D severities outside the penalty/tone tables fall through inconsistently

**Evidence:** `_parse_report` only admits severities in `_VALID_PP_SEVERITIES = {blocker,critical,major,minor,nit}` (`printproof3d.py:40,175`), so `assess_readiness` will only ever see those five. But `assess_readiness` independently re-defends with `_PP_PENALTY.get(issue.severity, 5)` (line 152, default penalty 5) and `_PP_RISK_TONE.get(issue.severity)` (line 153, default `None` → no risk). If the two modules ever drift — e.g. a sixth severity is added to the parser's allow-list but not to `_PP_PENALTY`/`_PP_RISK_TONE` — that issue would silently apply a 5-point penalty and surface *no* risk, which could let the score drop without a visible reason on the card.

**Why this matters:** Low probability (requires a future edit to one table but not the others), and the contract is currently consistent. But the defensive default (penalty applied, risk suppressed) is the one combination that produces a *silent* score change — the worst failure mode for an advisory card whose whole job is to explain itself.

**Fix path:** Make the `nit` exclusion explicit and treat any *other* unexpected severity as at least a `warn` risk so a penalty is never silent: e.g. `tone = _PP_RISK_TONE.get(issue.severity, "warn")` and skip only `nit`. Alternatively, derive both tables from a single ordered severity tuple so they cannot drift. No user-visible change today.

---

### ENG-703 (Minor / Hygiene) — `_GATE_BASE` / `_FALLBACK_VERDICT` default-on-unknown masks a would-be-impossible gate status instead of asserting it

**Evidence:** `smart_mesh.py:133` `score = _GATE_BASE.get(gate_status, 70)` and `pipeline.py:289` `tone = str(gate.status) if str(gate.status) in _FALLBACK_VERDICT else "warn"`. `gate.status` is a `Level` IntEnum that stringifies only to `pass`/`warn`/`fail` (`printability.py:42–48`), so the `.get(...)` defaults are unreachable. That's fine as defense-in-depth, but it means a future bug that produced an unexpected status (e.g. a refactor that passes a raw int) would be *silently absorbed* as a 70/warn card rather than surfaced.

**Why this matters:** Pure hygiene. The defaults are harmless today and arguably correct for a never-break card. Flagging only so the team knows the safety net would hide a real upstream bug rather than fail loudly in a dev/test build.

**Fix path:** Optionally, in the pure `assess_readiness`, keep the production default but add an `assert gate_status in _GATE_BASE` guarded by `__debug__`, or log once via the project's logger when the default branch is taken. Low priority; do not block on it.

---

### ENG-704 (Nit / Hygiene) — `material_profile` emits capability constants that don't affect `validate-model`, with no marker

**Evidence:** `printproof3d.py:209–233` (printer) and `:243–257` (material) hard-code capability flags (`supports_cancel`, `max_hotend_temp: 300.0`, `cooling_fan_speed_pct: 100.0`, etc.) as "conservative constants" because they don't affect model validation. This is documented in the module docstring and the inline comment, and the tests assert the required-field sets. The Nit: a reader auditing whether the *thermal window* fed to PrintProof3D is real (it is — derived from KimCad's configured temps, `:247–249`) has to cross-reference the docstring to know which fields are load-bearing vs filler.

**Why this matters:** Nothing breaks. It's a readability micro-cost on a security-relevant boundary (the profile JSON handed to an external engine).

**Fix path:** A one-line inline comment grouping the "model-validation-relevant" fields vs the "conservative constants" within each dict literal. Cosmetic.

---

## Things I explicitly checked and cleared (no finding)

- **Can readiness flip a gate-fail into a sliceable/sendable pass?** No. Slice (`webapp.py:1736`) and send (`webapp.py:1274`) refuse server-side on `gate_status_by_rid == "fail"`, recorded from `rep["gate_status"]` (`:1430`, `:1848`), which is the deterministic gate (`printability.py` `GateResult.status`). Readiness is never consulted in the slice/send guard. The gate-failed pipeline path returns *before* slicing unless `proceed_anyway`, and even then a gate-failed part is never *sent* (`_assemble_result`, `pipeline.py:525`). Invariant holds.
- **Does readiness ever contradict the gate verdict?** No. A gate FAIL forces `kc_tone="fail"` (`smart_mesh.py:170`) and the gate-fail risk is surfaced; tests `test_gate_fail_is_not_print_ready` and `test_gate_failed_run_still_attaches_readiness` confirm. The card can be *more* pessimistic than the gate (PrintProof3D piling on) but never more optimistic.
- **Bed-positioning mutating the shipped mesh?** No — operates on `hardened.copy()` (`pipeline.py:591`).
- **History blocking the live loop?** No — `record`/`comparison` are best-effort, swallow all exceptions, and the live-slider `rerender` passes `record_history=False` (`pipeline.py:712–713`) so a drag neither records nor runs the engine.
- **PII / network egress from the learning store or engine?** None found.
- **`os.replace` atomicity on Windows?** Correct — `os.replace` is atomic on both Windows and POSIX (`history.py:132`); the temp file shares the target's directory so it's a same-filesystem rename.

## What I could not check

- I did not execute the test suite or run the real PrintProof3D binary (none configured in this audit). All correctness claims are from static reading plus the existing tests' assertions, which I read in full and found to match the code. A live-assembled run with a real engine binary remains the right gate before promotion, per the project's evidence-altitude standard.
- I did not audit the frontend rendering of the readiness card / viewport highlight geometry (out of scope for the engine deep-dive; the UI/UX role covers it).

---

## Severity rollup

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 0 |
| Minor    | 3 |
| Nit      | 1 |
| **Total**| **4** |
