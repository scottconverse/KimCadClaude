# GauntletGate Full — UI/UX Designer — KimCad 0.9.2

**Role:** Senior UI/UX Designer
**Severity roll-up:** Blocker 0 · Critical 0 · Major 0 · Minor 1 · Nit 2

---

## Findings

### UIUX-MIN-001 · Minor — Ollama brand leak in ModelHealthPill user-facing copy (two strings)

**Category:** Brand leak / user-facing copy
**Evidence:** `frontend/src/components/ModelHealthPill.tsx:37,39`

Two user-visible strings in ModelHealthPill expose the "ollama" CLI command directly in the pill text rendered on the main workspace header:

```
line 37: `The model isn't downloaded yet — the setup wizard's Download button fetches it (or run "ollama pull ${model.model}").`
line 39: `Photos and sketches need one more download — the setup wizard's Download button fetches it (or run "ollama pull ${model.vision_model}"). Designing in words works now.`
```

These are rendered in a `<p className="kc-model-pill" role="status">` element visible on the main canvas when the model or vision model is missing. The test at `ModelHealthPill.test.tsx:52` positively asserts `ollama pull gemma4:e4b` appears in the pill — confirming this is intentional in the current code, not guarded away.

**Why it matters:** The product has explicitly eliminated every other "ollama" brand reference from user-facing copy (pipeline.py comment at line 200-201 calls this out; FirstRunWizard's cold-path test at `FirstRunWizard.test.tsx:192` asserts `queryByText(/ollama pull/)` is `null`). These two ModelHealthPill strings are survivors that contradict that intent. A non-technical user who never installed Ollama independently has no tray icon, no terminal muscle-memory, and no idea what "ollama pull" means. Receiving this instruction on the canvas header — which appears before a design attempt — is a dead-end for that user. The in-app wizard's "Download now" button exists precisely to replace this instruction; the parenthetical "(or run...)" acknowledges that but treats the CLI as co-equal.

**Inconsistency with Settings:** `SettingsPanel.tsx:425` also surfaces `ollama pull {model.vision_model}` in a `<code>` element, but in a secondary "not downloaded" note inside the Settings AI section — a more technical context where advanced users legitimately look. The pill appears on the workspace for *all* users.

**Fix path:** Remove the `(or run "ollama pull ${model.model}")` / `(or run "ollama pull ${model.vision_model}")` parentheticals from both pill strings. The primary path — "the setup wizard's Download button" — is sufficient. Update `ModelHealthPill.test.tsx:52` to assert the absence of "ollama pull" (matching the FirstRunWizard precedent). The `SettingsPanel.tsx:425` `<code>` usage is a separate judgment call (settings-panel technical context); this finding does not require changing it.

---

### UIUX-NIT-001 · Nit — Vocabulary mismatch: "engine isn't running" vs Settings' "local AI isn't running yet"

**Category:** Copy consistency
**Evidence:** `src/kimcad/pipeline.py:203` vs `frontend/src/components/SettingsPanel.tsx:457`

The `MODEL_UNAVAILABLE_MESSAGE` in the chat thread reads:
> "KimCad couldn't reach your local AI — **the engine isn't running**."

Settings' action line (line 457) reads:
> "Your **local AI isn't running** yet."

And the fallback in `designStatus.ts:81` reads:
> "Your **local AI isn't set up yet**..."

The object being named shifts across surfaces: "engine" (pipeline.py), "local AI" (Settings, designStatus.ts), and "AI" (ChatPanel.tsx:224: "Set up your local AI first — see Settings"). These are functional synonyms in product context but the inconsistency adds a tiny friction: a user who reads the chat error, goes to Settings as instructed, and sees different phrasing may momentarily wonder if the two things are related.

**Why it matters:** Minor UX roughness; not a dead-end. The recovery path works. But the product clearly has a preferred term — "local AI" — used in both Settings and the first-run wizard. "Engine" is a technical abstraction the user has no visual referent for.

**Fix path (optional):** Align `MODEL_UNAVAILABLE_MESSAGE` to the Settings vocabulary: "KimCad couldn't reach your local AI — it isn't running. You can restart it from Settings, then try again." One word change, preserves the approved Ollama-free framing.

---

### UIUX-NIT-002 · Nit — Settings "About & reset" nav link closes the panel (confirmed from WALKTHROUGH)

**Category:** Navigation / SPA routing conflict
**Evidence:** `frontend/src/components/SettingsPanel.tsx:244`; WALKTHROUGH.md WLK-NIT-001

The "About & reset" nav link uses `href="#set-about"`, which the SPA hash-router intercepts as a route transition, dismissing the Settings panel instead of scrolling to the About section.

This was observed live in the walkthrough: `aboutLink.href` = `http://localhost:8714/#set-about`; clicking returned to the landing page. The other nav links (`#set-printer`, `#set-aimodel`, etc.) presumably share this architectural exposure but are less likely to be clicked from a non-default scroll position — the About link is at the bottom of the nav group and is most likely to be the *only* item clicked without prior scrolling.

**Severity assessment (this lane):** Nit is correct. The About section is reachable by scrolling. The reset action itself still works. No user data is at risk; no workflow is blocked. However: if a user discovers the reset option via the nav link, clicks it, and gets bounced to the landing page, recovering their intent requires re-opening Settings and scrolling — a small but real annoyance. Keeping Nit (not Minor) because the About section is non-critical and the workaround is trivial.

**Fix path:** Replace the `<a href={`#${it.id}`}>` pattern in the nav map with a button or an `<a href="#">` + `onClick` that calls `document.getElementById(it.id)?.scrollIntoView({ behavior: 'smooth' })` and calls `e.preventDefault()`.

---

## What's working (specific and credited)

**The 0.9.2 error message is a genuine improvement.** The new `MODEL_UNAVAILABLE_MESSAGE` ("KimCad couldn't reach your local AI — the engine isn't running. You can restart it from Settings, then try again.") is clean, product-vocabulary, and actionable. Removing "Ollama" from this string eliminates the most prominent brand leak on the post-first-run critical path — when a user has been designing and the engine drops, this is the error they see.

**The recovery CTA ("restart from Settings") is actually achievable.** When the engine is down, Settings shows: "Your local AI isn't running yet." + a "Set up KimCad's AI" button that re-enters the first-run wizard. The instruction in the error message matches the control that exists. This is the correct test: if the button didn't exist, "restart from Settings" would be a dead-end. It isn't.

**The chat-panel "Try again" + secondary instruction is well-designed.** `ChatPanel.tsx:221-226` adds a one-click "Try again" button plus "Set up your local AI first — see Settings." below it — so the user gets both immediate retry affordance and a recovery direction without having to retype their prompt. This is the right pattern for a recoverable error on a multi-minute workflow.

**The ModelHealthPill pre-empts the worst-case wait.** Showing the warning *before* the user submits a prompt (rather than after a 3-minute pipeline run fails) is the right UX call. The structure — pill warns, "Check again" button, silent-when-healthy — is correct.

**Ollama elimination is nearly complete.** Searching all of `frontend/src/` for user-visible "Ollama" strings shows: every case is either a code comment, a test file, or an internal API type/status name (`ollama_down`, `ModelPullSnapshot.status`). The only user-visible leaks are the two `"ollama pull"` strings in ModelHealthPill identified above. That's a very high cleanup rate for a brand that was previously woven throughout the copy.

---

## Coverage gaps

- **Live engine-down state not exercised.** The walkthrough environment had system Ollama running; the chat-panel `model_unavailable` rendering and the "Try again" button were not observed live. Assessment is based on static + test evidence. The tests assert correct behavior; live observation would give higher confidence.
- **First-run wizard cold-path not re-verified for 0.9.2.** The 0.9.2 change surface does not touch the wizard, so the 0.9.1 valid cold attestation carries forward — but the ModelHealthPill brand leak (UIUX-MIN-001) would be visible on first-run if a user finishes the wizard and the model is not yet present. The pill appears on the workspace canvas, which is visible immediately after first-run completes.
- **SettingsPanel `ollama pull` in vision-model note** (`SettingsPanel.tsx:425`) was noted but not raised as a separate finding. It is in a technical sub-note within Settings and uses a `<code>` element — appropriate for that audience context. Left to engineering judgment whether to align it with the pill fix.
