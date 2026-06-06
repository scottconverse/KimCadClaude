# Slice 7 — Next-sprint watchlist

Forward-looking items that are explicitly **not** Slice-7 blockers (none gate this slice). Captured so they aren't lost.

| Item | Source role | Horizon | Note |
|------|-------------|---------|------|
| **Real-vision reading state.** On real gemma4:e4b CPU vision, "Reading your photo…" lasts meaningfully longer than the demo's sub-100 ms. The honest copy + `aria-live` are already in place. | UI/UX | **Slice 9** (the standardized no-frozen-spinner treatment) | Confirm a multi-second read still feels alive (progress cue) and the `aria-live` region isn't chatty enough to spam a screen reader. |
| **Older-Ollama empty-vision support path.** A too-old Ollama that ignores `think:false` returns empty vision, which presents like an unreadable photo. | Engineering | Post-stage / support | Now breadcrumbed to stderr (ENG-002). If a minimum-Ollama contract is ever added, consider a one-line "update Ollama" hint in the 422 copy (kept out of the consumer string for now — no jargon). |
| **Affordance text contrast margin.** The muted affordance label measures 4.66:1 on the page background — over the 4.5:1 AA floor but slim (5.14:1 on the card). | UI/UX | Ongoing | Belt-and-suspenders safe (the affordance is also bounded by a dashed border — shape, not color alone). Don't darken the page bg or lighten `--kc-muted` without re-checking. |
| **Optional-engine one-click-enable (CadQuery / PrintProof3D).** Listed under Slice 6 in the plan but deferred. | Docs/Plan | **Stage 8** (where CadQuery lands) | Marked as deferred in `docs/stage-8.5-usability-plan.md`. The Settings screen's "discover the optional engines" goal is partially met (tools health) — the install/enable management arrives with the engine itself. |
| **Stage-end doc consolidation.** The per-slice builds historically updated audit artifacts but not the prose docs; this audit cleared the backlog (CHANGELOG/README/HANDOFF/ARCHITECTURE/plan now current through Slice 7). | Docs | Stage-end | Keep the prose docs current per-slice going forward to avoid the debt re-accumulating ("one truth per doc"). |
