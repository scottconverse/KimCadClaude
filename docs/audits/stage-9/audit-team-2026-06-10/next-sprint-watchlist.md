# Stage 9 gate — next-sprint watchlist (Stage 10+)

Forward-looking items. None are open defects; each is a decision or debt to handle when the
named work starts.

1. **Flatten the `DesignRegistry` alias seam (Stage-10-start, already scheduled).** `webapp.py`
   still binds local names to `reg.*` fields ("transitional seam"). Stage 10's router split is
   the moment to remove the aliases entirely; the TEST-003 pins will catch any half-rebind.
   *(Engineering)*

2. **QA-902 — an aborted vision read can't cancel the in-flight Ollama generation.** Accepted
   and documented for Stage 9 (~20–30 s reads). If Stage 10/11 lengthens reads (bigger images,
   slower boxes) or adds retry automation, revisit: Ollama's API has no per-request cancel;
   options are a per-model queue with a "busy" surface, or `keep_alive`/connection-drop
   experiments. *(QA)*

3. **Settings screen: a vision-model row.** `/api/model-status` now reports
   `vision_model`/`vision_present` and the wizard + health pill consume it, but the Settings
   "AI model" card still shows only the design model. Add the second row when Settings is next
   touched (Stage 10 wizard work is adjacent). *(UI/UX)*

4. **Wizard model-pull-with-progress (planned Stage 10) must cover BOTH pulls.** The Stage 10
   plan predates the second model; the progress UI should pull `gemma4:e4b` and `qwen2.5vl:3b`
   (~13 GB total), with per-model progress and a usable-without-vision intermediate state.
   *(UI/UX + Engineering)*

5. **Control-plane banner sweeps as a stage-gate step.** DOC-002 happened because correction
   banners themselves went stale. Add to the stage-gate checklist: grep the design plane for
   claims the stage just overturned (e.g. `grep -ri gemma docs/design`). *(Writer)*

6. **Installer disk math (Stage 11).** The 20 GB guidance assumes two models + tools + venv.
   The Stage 11 bundled installer should check free space before the pulls and fail friendly —
   mid-pull disk-full is the one failure class troubleshooting has no entry for. *(Engineering)*

7. **Cloud-backend vision status is unknowable in-band.** `/api/model-status` omits
   `vision_present` when the chat backend is cloud (the vision model is still local but isn't
   probed). If cloud users report confusing on-ramp failures, add a separate local-Ollama probe
   for the vision model even when chat routes to the cloud. *(Engineering)*
