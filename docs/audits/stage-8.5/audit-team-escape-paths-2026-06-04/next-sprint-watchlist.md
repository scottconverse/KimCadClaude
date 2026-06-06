# Escape-paths stage — Next-sprint watchlist

Forward-looking items deliberately NOT in this stage (none gate it). Tracked as tasks.

| Item | Source | Note |
|------|--------|------|
| **Global request timeout ("nothing hangs forever").** | Eng/UX | Deferred to its own slice — combining a timeout signal with the user signal without breaking the signal-forwarding contract is a deliberate cross-cutting change. The per-action Cancels already remove every trap; this is the backstop. |
| **Esc-everywhere + modal Esc-to-close.** | UI/UX | Only the design overlay honors Esc today; fold "Esc cancels the active in-flight action" (photo/slice/import) and "Esc closes any modal" into a follow-up. Confirms (delete/reset) already have Cancel. |
| **True server-side cancel.** | QA/Eng | Client-abort releases the UI; the local job (OrcaSlicer, the vision/codegen model) finishes its current pass in the background — honest + documented. A real server-side cancel (e.g. interrupting the Ollama runner) is a later improvement. |
| **Slice 9 overlap.** | Docs | This stage pulled the design overlay's honest-progress + elapsed forward from Slice 9 ("real progress on long runs"). Slice 9 should fold in the richer step indicator (planning → generating → rendering → validating) and the model-down wall, not re-do the cancel. |
