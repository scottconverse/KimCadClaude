# Stage 7 — Next-Sprint Watchlist

Forward-looking items that are out of scope for the Stage-7 tag but should be tracked. None blocks
the tag; each is a deliberate boundary or a scaling concern surfaced by the audit.

1. **Fold a PrintProof3D `fail` into the slice gate — once the engine ships enabled.** Today the
   deterministic gate is the slice authority and PrintProof3D is advisory, so a part the engine
   fails but the gate passes is still sliceable while the card reads "Not print-ready." In every
   *default* config (engine off) the card and the slice affordance agree exactly; they can only
   diverge once the engine is enabled by default. Reconcile then (gate the export on a fail verdict,
   or a proceed-anyway-style confirm). *(Eng / UI-UX — surfaced across Slices 3–5 audits.)*

2. **Cross-process history lock if multi-instance ever matters.** The Stage-7 fix makes `record`
   atomic + serialized *within* a process. Two separate KimCad processes racing can still drop a
   record (never corrupt the file). Fine for a single-user local app; revisit with an OS advisory
   file lock only if a multi-instance scenario appears. *(Eng — ENG-701 follow-up.)*

3. **A recency window for the comparison.** The "compared to your past parts" line ranks against the
   full all-time history. Once a user accumulates hundreds of parts, a "recent N" or time-bounded
   pool may read more usefully; `created_at` is already stored for this. *(Eng — ENG-704 follow-up.)*

4. **Live engine-on slider latency.** The live-slider re-render computes a fast gate-only readiness
   and deliberately skips the engine subprocess. If a future UX wants engine depth on a drag, it
   must be async/debounced — a synchronous 120 s-timeout subprocess per drag would be a UX cliff.
   *(Eng / UI-UX — Slice 3 follow-up.)*

5. **No E2E browser test for the readiness card.** The card is covered by vitest component tests +
   live DOM/computed-style checks, which is acceptable at this altitude; a real browser E2E (once a
   working headless screenshot path exists in CI) would harden the rendered layer. The JPEG
   screenshot tool times out in the current environment. *(Test / QA.)*

6. **`MeshReadiness` value-comparability.** The purity test relies on the dataclass staying
   value-comparable; if it ever gains a non-compared field or is tuned `eq=False`, revisit the
   determinism assertion. *(Test — TEST-S7-004.)*
