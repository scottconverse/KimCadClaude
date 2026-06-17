# KimCad — Cold-Start & Onboarding UI/UX Audit

**Date:** 2026-06-17
**Skill:** coder-ui-qa-test (Senior UI Designer lead · Principal Engineer · QA)
**Build under test:** released `main` @ `e7deafb` (0.9.0b4 + restored designer pass)
**Method:** the **real app** (`kimcad web`) driven via Playwright in a **true cold-start state** —
fresh profile, **Ollama unreachable** (`/api/model-status` → `backend:local, running:false,
model_present:false`), reproduced by pointing the local backend at a dead loopback host. This is
the new-user path **no prior audit ever walked** (every prior audit box had Ollama already running —
the same blind-spot shape as the b5 false-green, relocated to onboarding).

---

## Verdict

The released product is **unusable out-of-the-box for a new user** until they manually discover,
download, and install a **separate program (Ollama)**, start it, return, poll a "check again"
button, and then wait on a **10–13 GB** model download — with **no in-app automation of any of it.**
The wizard step literally titled **"Set up your AI" does not set up the AI**; it hands the user
homework and a polling button. This is the single biggest reason a new user bounces, and it is the
root of Scott's report that "the user journey sucks."

There is also a real correctness bug behind it: the local-vs-cloud detection keys off the literal
string `"11434"` in the backend URL, so a user whose Ollama runs on any non-default port is
**falsely told the AI is "ready"** and then hits a design failure.

## Severity roll-up

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 1 |
| Minor | 3 |

---

## Findings

### [UX-COLD-001] — Critical — Onboarding dead-ends a new user; "Set up your AI" sets up nothing

**Evidence (live, cold app):**
- Wizard step 2 **"Set up your AI"** renders (screenshot on file): *"KimCad local AI qwen2.5:7b — Ollama isn't running … KimCad's AI runs on Ollama (free). Don't have it yet? **Get Ollama** — install it, let it start, then **check again**. Already installed? Just start it."*
- Landing banner: *"Your local AI isn't running yet — start Ollama to design."* + a **Check again** button.
- The **"Design it" button is `disabled`** while the AI is down. The TRY example chips remain present.
- `/api/model-status` cold: `{backend:"local", running:false, model_present:false, vision_present:false}`.

**Why it matters:** The entire value proposition ("describe a part → get a print") is **unreachable on a fresh machine** without a multi-step manual detour to ollama.com, a full Ollama install (tray app + background auto-updater service), a manual start, a "check again" poll, and a 10–13 GB model download. The one wizard step whose job is to *set up the AI* instead delegates that work to the user. Even an expert is disoriented; a layperson abandons.

**Blast radius:** Every first-run user on a machine without Ollama (i.e. ~all of them). Touches `FirstRunWizard.tsx` (step 1), `Landing.tsx` (cold banner + disabled Design), and the install story (installer final-page note + install-guide/README/FAQ/USER-MANUAL/getting-started/troubleshooting all currently say "go install Ollama yourself").

**Fix (approved — Plan B):** KimCad **manages a headless Ollama** itself: reuse a system Ollama if present, else **auto-fetch the portable `ollama-windows-amd64.zip`** (verified hash) into KimCad's data dir, run `ollama serve` as a managed subprocess (`OLLAMA_MODELS` in KimCad's dir), health-check it, and shut it down with the app. The wizard "Set up your AI" step becomes **one real action** — "Set up KimCad's AI" — that ensures the runtime then downloads the model in a single honest progress flow. **No ollama.com, no manual install, no "check again."** (Builds on the existing `scripts/ollama_watchdog.py` locate+serve logic and `model_pull.py` in-app download.)

---

### [ENG-COLD-002] — Major — Local-Ollama detection misclassifies any non-default port as "cloud, ready"

**Evidence:** `webapp.py:_handle_model_status` →
```python
is_local = backend is not None and (backend.provider == "ollama" or "11434" in base_url)
```
The shipped local backend's `provider` is the OpenAI-compatible client (not literally `"ollama"`), so detection relies **solely on the substring `"11434"`** in `base_url`. Confirmed live: changing the port to `:11499` flipped the app to `backend:"cloud", running:true, model_present:true` — a false "ready." A user who runs Ollama on a custom port (`OLLAMA_HOST=…:11500`) gets the same false "ready," then their first design fails with a model-unreachable error.

**Why it matters:** Silently reports a broken/cloud state as a working local one — the dishonest-status failure mode the project's own UX rules forbid. Also defeated my own cold-start repro until diagnosed.

**Blast radius:** `_handle_model_status` (and any consumer of its `backend`/`running` fields: the wizard, the landing cold banner, the ModelHealthPill, Settings). Fix: classify "local" by **loopback host** (parse the URL host, `ip_address(host).is_loopback or host=="localhost"`) — mirroring the rigor already in `model_pull.is_loopback_url` and `config._is_local_base_url` — not by a port substring, and probe accordingly. Folds naturally into the managed-runtime work.

---

### [UX-COLD-003] — Minor — Cold landing leaves the prompt + TRY chips interactive-looking while Design is disabled

**Evidence:** Cold landing: `Design it` is `disabled`, but the prompt textarea and the three TRY example chips remain visually active. A user can type or click a chip and nothing happens beyond the disabled button + banner.

**Fix:** When the AI is unavailable, point the cold state at the *fix* — e.g. the banner's primary action becomes "Set up KimCad's AI" (the new one-click flow) rather than only "Check again"; consider visually quieting the chips until the AI is ready.

---

### [QA-COLD-004] — Minor (test-harness fidelity) — `USERPROFILE` override in the audit launch configs does not isolate the profile

**Evidence:** The cold launch config set `USERPROFILE=…\kimcad-cold-home`, yet `/api/settings` returned the **real** `~/.kimcad/settings.json` (the real Bambu/OctoPrint connectors + `cloud_enabled:true`); the cold home stayed empty. So the prior "isolated" walkthroughs (`kimcad-walk*-home`) likely ran against the **real** profile too.

**Why it matters:** Not user-facing, but it means audit isolation was illusory — a contributor's real settings can leak into a "clean" walkthrough and mask first-run states (it masked this one initially). Fix: give the app/test harness a first-class config-home override the launcher actually honors, or verify `USERPROFILE` propagation in the harness.

---

### [UX-COLD-005] — Minor — Model-download size is quoted 10–13 GB at the moment of highest abandonment risk

**Evidence:** Cold wizard offers *"Download now (~13 GB)"*; docs quote 8/9/13 GB inconsistently (prior DOC-002). The real pair is ~7.7 GB.

**Fix:** Pin one measured figure (~7.7 GB) across wizard + docs; in the new one-flow setup, start the **chat** model first and let the user begin designing the moment it lands ("words work now; the photo/sketch reader keeps downloading"), so the headline wait is ~4.7 GB, not 13.

---

## Remediation plan (this sprint)

1. **`ollama_runtime.py`** — managed headless Ollama: locate system → else fetch+verify+extract portable zip → `ollama serve` (managed, `OLLAMA_MODELS` in KimCad dir) → health-check → shutdown. (TDD; builds on `ollama_watchdog.py`.)
2. **Wire into `shell.py` + `serve`** — start/ensure on launch; clean teardown.
3. **Fix [ENG-COLD-002]** — loopback-host local detection in `_handle_model_status`.
4. **`/api/ensure-ai`** (or extend model-pull) — one action: ensure runtime → pull model, unified progress.
5. **Wizard step-1 redesign** — one "Set up KimCad's AI" action; kill the ollama.com detour + "check again."
6. **Cold-landing** ([UX-COLD-003]) — primary action routes to setup.
7. **Docs + installer note + size figure** ([UX-COLD-005]); **tests**; **Hard-Rule-9 deliverables** synced; full gate; Verification Log.

Drive every finding to 0/0/0/0/0.
