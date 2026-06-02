# Stage 6 — Next-Sprint Watchlist

Forward-looking items that don't block the Stage 6 gate but should be tracked.

- **The advisor-vs-bake-off "two notions of better" seam (from UX-003).** The `models` advisor ranks by a static `tier` integer; the bake-off measures actual results. They can disagree (the advisor would happily suggest a qwen the bake-off rejected). UX-003 softens the wording this sprint, but the deeper fix — having the advisor *defer to* a recorded bake-off result for models it has measured — is a real future improvement once bake-off results are persisted in a form the advisor can read.

- **`alt_backend` user documentation (from ENG-605).** The tiered fallback ships off by default (`alt_backend: null`). When it's documented for users, the doc must note the thread-local stickiness behavior: once a long-lived web worker falls back to the alt, it stays there until the process recycles, so a recovered primary resumes on the next fresh worker / restart, not mid-session. This is the right design for a dead primary; it just needs to be stated so an operator isn't surprised that a web session stays on cloud after Ollama comes back.

- **`Recommendation` name as the model layer grows (from ENG-602).** Renamed to `BakeoffDecision` this sprint. If the model layer keeps growing (Stage 7+ model-quality work), keep the two verdict types (`model_advisor.Recommendation`, `bakeoff.BakeoffDecision`) clearly distinct; resist a shared `Recommendation` base unless they genuinely converge.

- **`_ollama_tags_url` robustness (from ENG-601).** Hardened this sprint to `urlsplit`. If a future flow ever lets a user pass a base_url with a sub-path (a reverse-proxied Ollama behind a path prefix), re-verify the reconstruction handles it — the conventional local URLs are covered, an exotic proxy path is the edge to watch.

- **Bake-off command-path test depth (from the TEST-00x cluster).** The pure decision core is exhaustively tested; the CLI front-door (`_cmd_bakeoff` validation, `_pipeline_for_backend` isolation) was the thin spot, closed this sprint. As `kimcad bakeoff` grows options (more backends, persisted results), keep the command-path tests in step with the pure-core tests.

- **Benchmark prompt-set size.** The done-gate is still the 10 Appendix-B prompts. A larger, more diverse prompt set (deferred from Stage 6) would make both the done-gate and any future bake-off a stronger signal — worth scheduling when model-quality work resumes.

- **gemma's CPU latency (~10 min/prompt).** Not a defect and explicitly out of scope, but it's the practical ceiling on how often a full live bake-off or benchmark can be run on the target box. Any future "re-run the bake-off" cadence has to budget for it; a faster target box (if one ever arrives) changes the calculus.
