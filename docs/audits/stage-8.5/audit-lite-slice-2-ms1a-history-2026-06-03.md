# Audit Lite — Stage 8.5 Slice 2, MS-1a (conversation-history threading)
**Date:** 2026-06-03
**Scope:** Uncommitted working-tree change to `src/kimcad/webapp.py` + `tests/test_webapp.py` — a `_sanitize_history` helper that coerces/bounds client-supplied conversation history, and the plumbing that threads it through `design_response` → `pipeline.run` → `generate_design_plan` for a follow-up/refine turn.
**Reviewer:** Claude (audit-lite)
**Posture:** Balanced, security + correctness weighted (untrusted client input threaded to the model).

## TL;DR
Ship. The change is small, total, and correct. `_sanitize_history` is genuinely defensive — fuzzed with ~18 hostile input classes (None/str/int/bytes/nested junk/100k-list/non-str roles+content/missing keys/control chars) and it never raised and never leaked a malformed turn. The bound bounds (20 most-recent turns, 4000 chars/turn), threading reaches `generate_design_plan` end-to-end, `history=None` reproduces the old standalone call exactly, a malformed history is dropped (never a 400/500), and the injection invariant holds — client history is model-context only and never reaches OpenSCAD emit or the sandbox. No Blocker/Critical/Major findings.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 1

## Findings

### NIT-001 Nit: 100k-element list is fully materialized before the 20-turn slice
**Dimension:** Correctness / Security
**Evidence:** `webapp.py:158` — `for turn in raw[-MAX_HISTORY_TURNS:]`. The slice only keeps the last 20, but the whole list is received and held first. In isolation a huge `history` array is a memory-amplification vector.
**Why it matters:** It does not actually bite: `_read_json_body` enforces `MAX_BODY_BYTES = 1 MiB` (webapp.py:670) and returns 413 *before* `_handle_design` ever calls `_sanitize_history` (webapp.py:853), so an oversized history can't arrive over HTTP. The DoS surface is already closed at the body-size layer; the turn cap is a second, independent bound on prompt-context size. Mentioned once for completeness, not a defect.
**Fix path:** None required. (If ever called off the HTTP path with an unbounded source, slice-by-count is already O(20) on the kept set; the input list size is bounded upstream.)

## What's working
- **Totality / never-raises:** direct fuzz over None, `"str"`, `5`, `3.14`, `True`, `b"bytes"`, a dict-not-list, tuple, set, lists of `None`/ints/`[]`/`{}`/partial dicts, a 100k-element list, extra+unhashable keys, case/whitespace-variant roles, list/dict content, bytes role, int keys, and control/`<script>` chars — **zero exceptions; every result was either `None` or a correctly-shaped bounded `[{role, content}]`** (`webapp.py:151-165`).
- **Leak-proofing:** output is rebuilt as `{"role": role, "content": content[:CAP]}` (webapp.py:162), so extra keys are stripped, role is whitelisted to `user`/`assistant`, and content is forced to a capped `str`. Nothing malformed reaches the model.
- **Bound bounds + most-recent:** `raw[-MAX_HISTORY_TURNS:]` keeps the 20 newest turns and `content[:MAX_HISTORY_CONTENT]` caps each at 4000 chars — both verified empirically (50-turn input → last turn `"49"`; 9999-char content → 4000).
- **Threading correct end-to-end:** `pipeline.run(prompt, out_dir, history=history)` (webapp.py:182) → `generate_design_plan(prompt, printer, material, history=history)` (pipeline.py:338-339). HTTP test confirms good turns arrive at `generate_design_plan` and a bogus-role turn is dropped.
- **No behavior change for first-turn flow:** `history` defaults to `None`; `design_response`/`run` with `history=None` is the pre-change call. Existing 62 tests unchanged and green.
- **Injection invariant holds:** the client `history` only feeds `generate_design_plan`. The OpenSCAD path (`_build_geometry`, pipeline.py:719-720) uses its own *fresh internal* `thread: list[dict[str,str]] = []` render-repair loop — client history never reaches `generate_openscad` or the deterministic template emit (`_build_from_template`), where only clamped numeric plan values flow. Control/`<script>` chars in history are passed through as inert model-context text, never code.
- **Tests are non-vacuous:** unit test pins None/non-list/empty→None, drops (bad role / non-str content / non-dict), order preservation, turn cap (most-recent), and content cap. HTTP test is a real socket server (`_serve` + `urllib`) via a `Recording(FakeProvider)` that captures the `history` actually delivered to `generate_design_plan`, and exercises absent→None and non-list→None.

## Watch items
- If MS-1b later threads `history` into any path that *emits* (codegen, file names, sandbox), the injection-safe invariant must be re-audited — today it is model-context only.

## Escalation recommendation
No escalation needed. Tiny, well-scoped, fully covered change with one Nit that is already mitigated upstream. `pytest tests/test_webapp.py -q` → **63 passed**.
