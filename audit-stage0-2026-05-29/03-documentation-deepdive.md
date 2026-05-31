# 03 — Documentation Deep-Dive

**Role:** Technical Writer
**Project:** KimCad
**Audit:** Stage 0 (pre-merge/tag)
**Date:** 2026-05-29
**Scope:** `README.md`, `CHANGELOG.md`, `ROADMAP.md`, `HANDOFF.md`, `audit-lite-web-ui-2026-05-29.md`, inline docstrings/comments in `src/kimcad/*.py`, and `config/default.yaml`. Cross-checked against code reality.

---

## TL;DR

The docs are, on the whole, well above the bar for an early-stage project: the README reads cleanly in under 60 seconds, the inline docstrings are some of the best I've audited (they explain *why*, not just *what*), and ROADMAP/CHANGELOG are honest about what hasn't happened yet. But there is one **Blocker**: the README's and HANDOFF's model-setup instructions still pull `gemma3:12b`, while the code now runs `gemma4:e4b` — so a user who follows the README installs the wrong model and the pipeline calls a model that isn't present. There is also a **Critical honesty problem** baked into a config comment that claims real-print validation that, per the project's own ROADMAP, has not happened. Both are doc-drift from the Stage-0 model switch and a relocation-of-hardware reality. Everything else is Major-and-below.

---

## Severity rollup

```
Blocker:  1
Critical: 1
Major:    4
Minor:    3
Nit:      2
-----
Total:   11
```

---

## Findings

### DOC-001 — Blocker — Accuracy
**README and HANDOFF tell the user to install the wrong model; the code calls a model the user never pulled.**

**Evidence:**
- `README.md:66` — the setup section instructs: `ollama pull gemma3:12b`, immediately followed by "That is all the LLM setup required."
- `HANDOFF.md:38` — resume step 1: "Confirm `gemma3:12b` is present: `curl http://localhost:11434/api/tags`".
- `config/default.yaml:29` — the active `local` backend is `model_name: gemma4:e4b`.
- `cli.py` / `llm_provider.py` send `self.backend.model_name` (i.e. `gemma4:e4b`) to the Ollama endpoint with no fallback to `gemma3:12b`.
- The CHANGELOG already records the switch: `CHANGELOG.md:50-51` ("Default local model is now `gemma4:e4b` … `gemma3:12b` … is no longer used"), and ROADMAP and config comments all moved to e4b — README and HANDOFF are the two files left behind.

**Why this matters:** This is the canonical doc-Blocker: *the documented install does not work.* A first-time user runs the exact command in the README, pulls a 12B model the tool never calls, then runs `kimcad "..."` and gets an Ollama "model not found" error for `gemma4:e4b` — with no breadcrumb, because the README never names e4b anywhere. They've also downloaded a multi-GB model that is, per the project's own docs, too big and slow for the target hardware (the precise failure mode Stage 0 exists to eliminate). The returning developer following HANDOFF hits the same wall on resume. README never mentions `gemma4:e4b` at all, so there's no way to self-correct from the docs.

**Blast radius:**
- Adjacent docs: `HANDOFF.md:38` (same wrong pull target) and `HANDOFF.md:42` (the "~2 h on CPU" benchmark estimate is a gemma3:12b figure; ROADMAP says e4b makes the run "minutes" — fix in the same pass, see DOC-005).
- Shared state: the model name lives correctly in `config/default.yaml:29`; the docs are the only stale copies. No code change needed — this is a docs-only fix.
- User-facing: every new install and every HANDOFF-driven resume.
- Migration: none. Replace `gemma3:12b` → `gemma4:e4b` in `README.md:66` and `HANDOFF.md:38`, and add one line to the README naming e4b as the default and noting it's sized for the 32 GB / 780M target.
- Related findings: DOC-002 (same Stage-0 drift, honesty axis), DOC-005 (HANDOFF staleness).

---

### DOC-002 — Critical — Accuracy / Honesty
**A config comment claims "real-print validated" on hardware that, per the project's own ROADMAP, has never produced a real print.**

**Evidence:**
- `config/default.yaml:59` (Bambu P2S) and `config/default.yaml:65` (Elegoo Neptune 4 Max), both: `reference_hardware: true   # Scott has this unit — real-print validated`.
- `ROADMAP.md:17-22` directly contradicts this: "Printers live at Kim's house, not here. … *all* real-hardware validation — every real print, every live printer connection — happens **only in the final beta phase (Stage 10)**. Everything before that is built and tested against mocked/emulated printers."
- `ROADMAP.md:31`: "No installer, no printer connectivity, no image input, no real print."
- The comment also asserts "Scott has this unit," while ROADMAP says the printers (Bambu P2S/A1 and several Elegoo) are Kim's, off-site.

**Why this matters:** This is the honesty failure the writer rubric calls out as a Critical-or-Blocker pattern: a doc implying a capability/validation that does not exist. It's in a config file a contributor reads to understand the hardware model, and it's load-bearing — `reference_hardware: true` could plausibly gate "trust this profile" logic later. "real-print validated" is a strong claim; no real print has occurred anywhere in the project. Left in, it will (a) mislead a new contributor into thinking the P2S path is metal-verified, and (b) undercut the project's otherwise-careful honesty posture the moment someone cross-reads it against ROADMAP. I'm rating this Critical rather than Blocker only because it's an internal comment, not user-facing marketing copy.

**Blast radius:**
- Adjacent code: the `reference_hardware` field is parsed in `config.py:104` (`Printer.reference_hardware`); confirm no logic treats it as "verified on metal." If it's purely descriptive today, the fix is comment-only.
- Shared state: both printer entries carry the identical false comment — fix both.
- User-facing: none directly; this is contributor-facing trust.
- Migration: none. Recommend rewording both comments to something true, e.g. `# Kim's hardware (off-site); profile/build-volume VERIFY pending, no real print until Stage 10` and either renaming the field to `default_profile` or documenting that `reference_hardware` means "primary target profile," not "validated on metal."
- Related findings: DOC-001 (sibling Stage-0 drift).

---

### DOC-003 — Major — Accuracy
**The `server:` config block (host/port 8080) is dead and contradicts the actual web-UI port (8765) documented everywhere else.**

**Evidence:**
- `config/default.yaml:80-83` defines `server: { host: "127.0.0.1", port: 8080 }`.
- `webapp.serve` (`webapp.py:204-209`) defaults to `port: 8765` and never reads `config["server"]`; `cli.py:65` sets `--port` default `8765`; `README.md:96` documents `http://127.0.0.1:8765`.
- So the `server.port: 8080` value is never consulted, and the one number the user might copy from `default.yaml` is wrong by 285.

**Why this matters:** A returning user who opens `default.yaml` to "find the port" gets 8080, browses there, and sees nothing — the server is on 8765. The README told the spec to read `config/default.yaml` for "the shape" (`README.md:72, 86`), so the config is positioned as authoritative, but this block is stale config debt that lies. Either wire `serve()` to honor `server.host`/`server.port`, or delete the block.

**Blast radius:**
- Adjacent code: `webapp.serve`, `cli._cmd_web` — both hardcode 8765; `config.py` has no `server()` accessor, confirming the block is unused.
- User-facing: anyone consulting the config for the port.
- Migration: none. Recommend deleting the `server:` block (it's unreferenced) OR wiring it through `serve()` and aligning the default to 8765. Deleting is the smaller, honester fix.
- Related findings: none.

---

### DOC-004 — Major — Accuracy
**README CHANGELOG-style claim of a "five-module seed library" plus "eight new modules" does not match the 10 modules actually shipped.**

**Evidence:**
- `CHANGELOG.md:19-20`: "a five-module seed library (box, bracket, fasteners, fillets, mounts)".
- `CHANGELOG.md:37-41`: "eight new modules covering … wall and pegboard hooks, cable clip, closed box / two-part enclosure / tube, spool holder, and drawer divider."
- Actual: `library/` ships **10** `.scad` files and `library/manifest.yaml` declares **10** modules — the 5 seed files plus exactly 5 new files (`clips.scad`, `containers.scad`, `holders.scad`, `hooks.scad`, `organizers.scad`). 5 + 8 = 13 claimed; 10 exist.
- The "eight" is presumably counting *logical* part-families/signatures (hooks.scad alone exposes `wall_hook` + `pegboard_hook`; containers.scad exposes `snap_box` + `enclosure` + `tube`), but the prose says "eight new **modules**," and a module in this project = one `.scad` file in the manifest.

**Why this matters:** A reader counting modules to gauge coverage gets a number that's off by three and can't reconcile it with `manifest.yaml`. Per the doc-drift rule, a CHANGELOG entry that miscounts shipped artifacts is at least Major. The fix is trivial and the underlying work is real — this is a wording bug, not an overclaim of nonexistent features.

**Blast radius:**
- Adjacent docs: none repeat the count, but `README.md:152` describes `library/` generically ("seed OpenSCAD module library") and is fine.
- Migration: none. Recommend rewording to "five new module files (10 callable modules total): hooks (wall + pegboard), cable clip, closed box / enclosure / tube, spool holder, drawer divider," or count signatures consistently and say "thirteen callable modules across ten files."
- Related findings: none.

---

### DOC-005 — Major — Accuracy (staleness)
**HANDOFF.md is stale against the Stage-0 model switch: it pulls gemma3:12b, cites a gemma3-era 2-hour benchmark, and frames the done-gate around the old model.**

**Evidence:**
- `HANDOFF.md:38` — "Confirm `gemma3:12b` is present" (see DOC-001).
- `HANDOFF.md:42, 51` — "(~2 h on CPU)" / "a full 10-prompt run is ~2 h"; ROADMAP says e4b takes the loop "from ~2 h and unstable to minutes" (`ROADMAP.md:14, 39`).
- `HANDOFF.md:9` describes the open item as "a clean full-benchmark run scoring ≥ 8/10" without noting it must now pass *on e4b*, which ROADMAP (`ROADMAP.md:31, 37`) explicitly flags as "the real test, not the gemma3:12b runs."
- HANDOFF is dated 2026-05-29 (same day as this audit) but predates the model switch reflected in config/CHANGELOG/ROADMAP.

**Why this matters:** HANDOFF is the resume document — the first thing read after a reboot. Following it reconstructs the *old* gemma3:12b setup, re-introducing the exact slow/unstable loop Stage 0 was created to kill, and pulls a multi-GB model the tool won't call. It's internally inconsistent with the three docs that did get updated.

**Blast radius:**
- Adjacent docs: shares root cause with DOC-001 (the model switch). Fix HANDOFF and README in one pass.
- Migration: none. Recommend updating HANDOFF's resume steps to `gemma4:e4b`, replacing the "~2 h" estimates with the e4b "minutes" figure, and stating the done-gate must pass on e4b. Given HANDOFF is a transient reboot-pause artifact, consider whether it should be retired/archived once Stage 0 lands rather than maintained.
- Related findings: DOC-001.

---

### DOC-006 — Major — Completeness / Architecture
**No architecture document or diagram for a genuinely non-trivial pipeline.**

**Evidence:** The project is a multi-stage pipeline (prompt → plan → codegen → render → validate → gate → orient → slice) with injected LLM/renderer/slicer, a retry-feedback loop, and a web layer. The only "architecture" is the ASCII flow in `README.md:16-19` and the per-module docstrings. There is no `ARCHITECTURE.md` and no diagram of the data flow, the retry loop, or the trust boundary (untrusted LLM output → validated schema → sandboxed render).

**Why this matters:** A new contributor (the third persona) can orient from the excellent docstrings, but the *system-level* picture — how `pipeline.py` coordinates `llm_provider` / `openscad_runner` / `printability` / `orientation` / `slicer`, where the safety gates live, and the prompt→plan→code feedback loop — has to be reassembled by reading six files. For a project explicitly planning to grow (Stages 1–10, MCP connectors, a second CadQuery backend), a diagram is the highest-leverage doc to add now, before the graph gets harder to draw. The writer rubric flags absence of an architecture doc/diagram for a non-trivial system as a finding; given complexity here it's a Major, not Critical, because the README flow + docstrings partially cover it.

**Blast radius:**
- Adjacent docs: would absorb and de-duplicate the README flow diagram and the threat-model references scattered across docstrings (`pipeline.py:12-16`, `webapp.py:14-17`, `slicer.py:12-13`).
- Migration: none. Recommend a short `ARCHITECTURE.md` with one Mermaid sequence/flow diagram of the pipeline + the trust boundary, and a one-line module map. Audit+draft mode could produce it; flagged here as the gap.
- Related findings: none.

---

### DOC-007 — Minor — Accuracy (stale comment)
**`cli.py` module docstring describes only `design` and `bench`; the `web` verb it implements is omitted from the usage block.**

**Evidence:** `cli.py:3-7` lists `kimcad "..."`, `kimcad design …`, and `kimcad bench …`, but not `kimcad web …`, even though `_SUBCOMMANDS` (`cli.py:24`) includes `web`, the parser builds it (`cli.py:63-72`), and `_cmd_web` exists (`cli.py:152-156`). The README *does* document `web` (`README.md:88-108`) — this is a docstring lagging the code, not a user-facing gap.

**Why this matters:** Minor: it only misleads a contributor reading the module header, and the parser/README are correct. Worth a one-line fix for consistency.

**Fix path:** Add `kimcad web [--demo --port ...]` to the `cli.py` docstring usage list.

---

### DOC-008 — Minor — Accuracy (stale comment)
**`cli.py` docstring says missing prerequisites "fail with a plain-English message … rather than a traceback," but only `RuntimeError` is caught — a missing benchmark/prompt path and config-load errors can still surface raw.**

**Evidence:** `cli.py:11-13` promises plain-English failure for "no API key, no prompt file." Reality: the no-API-key path *is* handled (`llm_provider.py:100-104` raises `RuntimeError`, caught at `cli.py:174-177`). But `Config.load()` runs *before* the try block (`cli.py:166`), so a malformed/missing `default.yaml` throws a raw traceback; and the "no prompt file" case is handled by an explicit check in `_cmd_bench` (`cli.py:129-135`) returning exit 2, not by the exception handler the docstring implies. The claim is roughly true but imprecise.

**Why this matters:** Minor — the user-facing behavior is mostly fine; the docstring slightly overstates the safety net.

**Fix path:** Either move `Config.load()` inside the `try` and catch `FileNotFoundError`/`yaml.YAMLError`, or soften the docstring to "configured-backend and prompt-file errors fail with a plain-English message."

---

### DOC-009 — Minor — Completeness
**README never names the actual default model (`gemma4:e4b`) anywhere, so even after DOC-001 the "what model does this use?" question has no answer in the front-door doc.**

**Evidence:** Post-DOC-001, the only model name a user sees in the README is whatever the `ollama pull` line says. The README's LLM section (`README.md:30-72`) talks about "a local model" generically and points to `config/default.yaml` for "the shape," but never states the default is `gemma4:e4b` or why (the 32 GB / 780M target). That rationale lives only in ROADMAP and a config comment.

**Why this matters:** Minor (and largely subsumed by the DOC-001 fix), but worth calling out: the README should state the default model and one sentence of why, so a user understands what they're pulling and that it's deliberately small for their hardware.

**Fix path:** When fixing DOC-001, add: "KimCad defaults to `gemma4:e4b` — a ~4B-effective on-device model sized to run fast on a 32 GB / iGPU machine. Override in `config/local.yaml`."

---

### DOC-010 — Nit — Accuracy
**Test-count claim (119) is plausible but unverifiable from a static read and may drift.**

**Evidence:** `HANDOFF.md:13` and `ROADMAP.md:29` both state "119 tests." Static count of `def test_` across `tests/` is 112; `test_library_modules.py` uses `@pytest.mark.parametrize`, which expands the live count above 112, so 119 is plausible — I could not run pytest in this environment to confirm the exact number.

**Why this matters:** Nit — a hardcoded test count in prose is a maintenance trap that silently drifts every time a test is added. Not worth blocking.

**Fix path:** Either drop the exact number ("the suite passes, lint clean") or treat it as approximate ("~120 tests"). If the precise figure matters, regenerate it from `pytest --collect-only -q` rather than hand-maintaining it.

---

### DOC-011 — Nit — Accuracy
**README setup says `pip install -e ".[dev]"` then `python scripts/fetch_tools.py` "standard library only"; fetch_tools is stdlib-only but the README's framing ("no extra dependency") sits right after a dev-extras install that already pulled pytest/ruff.**

**Evidence:** `README.md:48-52` — "fetch the CAD/slicer binaries … (standard library only — no extra dependency)." True of `scripts/fetch_tools.py` in isolation, but at that point in the flow the user has already `pip install`-ed the package + dev extras, so "no extra dependency" reads slightly oddly in sequence.

**Why this matters:** Nit — purely a phrasing micro-smell; the statement is technically accurate about the script.

**Fix path:** Optional: reword to "(uses only the Python standard library — runnable even before the editable install)."

---

## What's working

Specific praise so the team keeps doing it:

- **The README front door is genuinely good.** `README.md:1-13` answers "what is this / who is it for / what's the status" inside five seconds, the pipeline flow (`:16-23`) is concrete, and the local-first / no-API-key posture (`:30-36`) is stated plainly and honestly. A first-time user knows within a minute whether KimCad is for them.
- **Inline docstrings are top-tier.** `pipeline.py:1-16`, `printability.py:1-12`, `slicer.py:1-22`, `ir.py:159-169`, and `cli.py:27-34` explain *why* — the trust boundary, why the dimensional tolerance is a flat 0.5 mm with no relative term (`printability.py:26-35`), why UTF-8 reconfigure is best-effort. This is the kind of comment that prevents a future contributor from "fixing" something that's intentional.
- **Honesty posture is strong where it counts most.** ROADMAP is unusually candid: `ROADMAP.md:28-31` ("Current baseline (honest)") states flatly that the done-gate hasn't passed, slicing isn't wired in, and there's no real print. The README's web section refuses to overclaim — `README.md:107-108` explicitly says G-code is *not* triggered from the UI yet rather than implying a full print path. The `audit-lite-web-ui` doc is similarly disciplined. (DOC-002 is the one place this posture slipped.)
- **The OrcaSlicer pin rationale is documented in three places and consistently.** `README.md:56-60`, `CHANGELOG.md:67-71`, and the `slicer.py` "KNOWN UNKNOWN" docstring (`slicer.py:15-21`) all explain the v2.4.0-alpha-over-2.3.2 decision with the upstream issue number. A future maintainer won't "upgrade to stable" and re-break CLI slicing.
- **The web-UI safety scope is documented honestly and matches the code.** README (`:107-108`) and `webapp.py:14-17` both state slicing is deliberately not triggered and G-code needs explicit confirmation — and `pipeline.py:261` confirms the slicer only runs under `confirm_print and self.slicer is not None`. Doc matches code exactly.
- **`config/default.yaml` carries VERIFY markers** (`:3, 20, 56, 58, 64`) flagging the values that still need real-binary confirmation. That's exactly the right way to ship honest placeholders — the reader knows what's trusted and what isn't. (DOC-002's "real-print validated" comment is the exception that breaks this otherwise-good pattern.)
- **CHANGELOG follows Keep-a-Changelog with a real Notes section.** The Added/Changed/Fixed/Notes split is clean, and the Notes block (`:67-71`) documents the one decision a reader would otherwise question. The `gemma4:e4b` switch *is* recorded here correctly (`:50-51`) — README/HANDOFF are the laggards, not the CHANGELOG.

---

## Doc-drift summary (the through-line)

Three of the four highest findings (DOC-001, DOC-002, DOC-005) share one root: **Stage 0 changed two facts about the world — the model became `gemma4:e4b`, and the hardware moved to Kim's house — and the propagation was incomplete.** Config, CHANGELOG, and ROADMAP absorbed both changes; README, HANDOFF, and one config comment did not. The single highest-leverage doc action in this audit is a "Stage-0 propagation sweep": grep every doc for `gemma3` and for any real-print/real-hardware claim, and reconcile each against config + ROADMAP. That one pass clears the Blocker, the Critical, and a Major together.
