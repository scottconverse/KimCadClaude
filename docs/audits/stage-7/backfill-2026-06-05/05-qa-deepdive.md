# Stage 7 — QA Engineer Deep-Dive (Smart Mesh Readiness)

**Auditor role:** Senior QA Engineer (independent, skeptical, runtime-focused)
**Date:** 2026-06-05
**Branch:** `stage-0-7-audit-backfill` (HEAD `800016a`)
**Method:** Exercised the readiness report end to end against the **live demo** (`http://127.0.0.1:8765/`, LLM-free) plus in-process synthesis runs of `assess_readiness` / `HistoryStore` for the paths the demo cannot reach (history is `None` on the demo by design). Every finding below was reproduced before it was written.

---

## Environment & what was tested where

- **Live demo server** (already running, demo provider, `history=None`): design POST, gate-fail design, slice refusal, send refusal, live-slider re-render, malformed/adversarial requests, NaN render input.
- **PrintProof3D engine:** **NOT present.** `config/default.yaml` points `binaries.printproof3d` at `tools/printproof3d/printproof3d.exe`, which does not exist, so `Config.printproof3d_binary()` resolves to `None`. Every live readiness verdict is therefore gate-only. This is the *intended honest-degradation* path, and it is the most important thing to verify: the card must not claim the engine ran. **It does not.**
- **In-process** (`.venv` + real modules): `assess_readiness` with injected `PrintProofReport`s (clean / major / blocker / nit-only / unknown-severity / 10-blocker), `HistoryStore.comparison` on a fresh store and after several parts, confidence/attribution matrix, score clamping.

I could **not** exercise the engine-fed (`confidence: High`, attribution "PrintProof3D validation engine") path through the *running* demo, because no binary is installed — that path was verified in-process instead. I could **not** exercise the live "compared to past parts" line through the demo, because the demo deliberately runs with no history store; verified in-process and against the real `HistoryStore`.

---

## What's working (credit where due)

The Stage 7 runtime is **solid**. The headline claims all hold up:

1. **The score is real synthesis, not hardcoded.** Gate-pass anchors at 92, gate-warn at 70, gate-fail at 38 (`_GATE_BASE`); PrintProof3D issues subtract a per-severity penalty (`blocker 60 / critical 45 / major 18 / minor 6 / nit 1`). Verified live (pass→92, fail→38) and in-process (major issue → 92−18=74; blocker → 92−60=32).
2. **Attribution is honest about the engine.** With no engine present, every live verdict reads `attribution: "KimCad printability gate"`, `confidence: "Medium"`, `sources: ["printability-gate"]`. It never claims PrintProof3D ran. When the engine IS injected, attribution flips to "PrintProof3D validation engine", confidence to High, and `sources` gains `printproof3d`. This is exactly the behavior the spec promises.
3. **The gate is authority.** A gate-FAILED part (`demo:gatefail`) carries a consistent fail readiness (score 38, "Not print-ready", fail-tone risks that mirror the actual gate findings) AND is refused at slice (`{"sliced": false, "reason": "gate_failed"}`) and send (belt-and-suspenders gate check at `webapp.py:1274`). The readiness card never contradicts the gate.
4. **Worst-of-two-signals verdict.** A PrintProof3D `status:"fail"` (or a blocker issue) forces "Not print-ready" even when KimCad's own gate passed — the card is never more optimistic than either signal. Verified in-process (blocker over a PASSING gate → score 32, "Not print-ready").
5. **The comparison is honest on a fresh store.** Empty history → `comparison: None` (the card shows nothing, no invented baseline). After several parts the line is factual ("A personal best…", "Below all N…", "Stronger than K of your N…", "On par…"). Same-type narrowing kicks in at ≥3 same-type parts; below that it compares against "all parts" and *says so*.
6. **Degradation never crashes.** Malformed bodies, wrong-typed prompts, unknown ids, non-dict render values, and `NaN` render inputs all return clean 4xx/200s — no 500, no traceback, no NaN in the score.
7. **No NaN / no negative score.** Score is integer-typed and clamped `[0,100]`; 10 stacked blockers → 0, not −508.

68/68 Stage 7 tests pass (`pytest -k "readiness or smart_mesh or history or printproof"`).

---

## Findings

### QA-701 (Minor) — A "Printable with notes" verdict can render with zero risks and no actionable note
**Category:** Flow / UX-honesty

**Evidence (in-process, reproducible):**
```
pp = PrintProofReport(status='warning', confidence_level='high',
                      issues=(PrintProofIssue('TINY_GAP','tiny','nit',(),None),))
assess_readiness(GateResult(findings=[]), <clean mesh>, material_name='PLA', printproof=pp)
# -> score 91, verdict 'Printable with notes', tone 'warn', risks [], recommendations ['Slice for PLA …']
```
Also reachable with `status='warning'` and **no issues at all** (score 92, warn, 0 risks).

The engine's overall `status` is folded into the tone independently of its issues (`pp_tone = warning → warn`, `smart_mesh.py:177-181`). But only `blocker/critical/major/minor` issues surface as card *risks* — `nit` (and a zero-issue warning) surface nothing. So the amber "Printable with notes" card shows a verdict and a confidence badge but **no risk and no specific recommendation** (only the generic "Slice for PLA…" boilerplate). The frontend compounds this: `RightPanel.tsx:414` renders the Risks section only when `risks.length > 0`, so the user gets an amber "something's off" signal with nothing to act on.

**Why it matters:** "Printable with notes" with no notes is a small honesty gap — it tells the user to be cautious without telling them why. Low exposure today (requires the engine present AND a nit-only/empty-issue warning), so Minor, not Major.

**Blast radius:**
- Adjacent code: `assess_readiness` tone logic (`smart_mesh.py:163-182`); card render guard (`RightPanel.tsx:414, 472`).
- User-facing: only the amber readiness card, and only when the engine runs and returns a bare warning.
- Migration: none.
- Tests to update: add a smart_mesh case asserting a warn verdict always carries ≥1 risk OR a synthesized "why" line.

**Fix path:** When `tone == 'warn'` (or 'fail') and `risks` is empty, synthesize a single neutral risk/line from the engine status (e.g. "PrintProof3D flagged a minor concern — see the detailed report") so the card never says "with notes" with no note. Alternatively, surface nit-level engine issues as a low-key risk.

---

### QA-702 (Minor) — An unrecognized PrintProof3D severity silently dents the score with no risk shown
**Category:** API / Synthesis-honesty

**Evidence (in-process):**
```
pp = PrintProofReport(status='warning', issues=(PrintProofIssue('X','x','weird_severity',(),None),))
assess_readiness(GateResult(findings=[]), <clean mesh>, printproof=pp)
# -> score 87 (92 - default penalty 5), risks 0
```
`_PP_PENALTY.get(issue.severity, 5)` applies a **default 5-point penalty** to a severity it doesn't recognize, but `_PP_RISK_TONE.get(severity)` returns `None` for that same unknown severity, so no risk is shown. The user sees a 5-point score drop with no explanation.

Note: the *wrapper* (`printproof3d._parse_report`, line 175) already **drops** issues whose severity isn't in the valid set, so an unknown severity can't reach `assess_readiness` *via the real engine* — this is only reachable if a future caller constructs a `PrintProofIssue` directly. That makes it Minor/defensive, not Major.

**Blast radius:**
- Adjacent code: `_PP_PENALTY` / `_PP_RISK_TONE` (`smart_mesh.py:33-35`); the parser's severity filter (`printproof3d.py:175`) is the real-world guard.
- Migration: none.

**Fix path:** Make the two maps consistent — if a severity isn't penalty-known, don't penalize it (penalty default 0) so the score and the risk list can't diverge; or surface unknown-severity issues at a neutral tone.

---

### QA-703 (Minor) — "On par" can read more flattering than the data when priors strictly beat the part
**Category:** History / honesty

**Evidence (in-process, `history.compare_phrase`):**
```
priors scores = [80, 90, 90], this part score = 80
-> "On par with your 3 past box parts."
```
The `ahead == 0` branch (`history.py:76`) returns "On par" before considering that two priors strictly beat this part. A part that *ties one* and is *strictly behind two* reads "On par with your 3 past parts" rather than acknowledging it sits at the bottom of the pack. The store's docstring explicitly promises wording that "never overstates", so this is a self-consistency gap with the module's own honesty contract.

This is genuinely borderline — "on par" is defensible (it did tie one), and the case needs a tie at the floor. Minor.

**Blast radius:**
- Adjacent code: `compare_phrase` ranking branches (`history.py:72-78`).
- Migration: none. Pure wording change.
- Tests to update: `tests/` history phrasing cases — add the tie-at-floor case.

**Fix path:** Reserve "On par" for when the part is not strictly below the majority (e.g. `behind <= ahead` or `behind == 0`); otherwise fall through to a "Stronger than 0 of N / behind most" wording.

---

## What I could not test, and why

- **Engine-fed live verdict (High confidence / "PrintProof3D validation engine" attribution):** no binary installed (`tools/printproof3d/` absent). Verified in-process with injected reports instead. Recommend a follow-up live run once a real PrintProof3D binary is dropped in, to confirm the subprocess wrapper + profile generation behave against the actual engine (the wrapper is well-guarded — never raises, degrades to `None` — but it has only been exercised against fakes).
- **Live "compared to past parts" line:** the demo runs `history=None` by design (so a UI check never pollutes the user's store). Verified the comparison engine in-process and against the real `HistoryStore` on disk. The full pipeline→history record→comparison loop is covered by the passing Stage 7 test suite, not by the running demo.

---

## Severity rollup

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 0 |
| Minor    | 3 |
| Nit      | 0 |

**Verdict:** Stage 7 readiness is **ready** from a QA/runtime standpoint. The load-bearing claims — synthesis-driven score, honest attribution when the engine didn't run, gate-as-authority, fresh-store comparison honesty, robust degradation, no NaN/no-500 — all hold under direct exercise. The three Minor findings are honesty/wording polish on edge paths (a noteless "with notes" card, a score/risk divergence on an unreachable-via-engine severity, and a borderline "on par" phrase); none block, and none can mislead a user into printing something the gate would refuse.
