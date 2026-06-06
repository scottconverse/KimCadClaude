# Stage 8.5 Stage-Gate — Next-Sprint Watchlist (forward-looking; not gate-blockers)

These are structural / forward items the roles surfaced that are NOT part of the this-gate
remediation (they're design debts, scaling concerns, or decisions to make deliberately later).

- **Real-browser e2e for the keyboard-shortcut flow.** The preview harness's isolated world can't
  trigger the app's window keydown listeners, so the "?" / n / d / , shortcuts are unit-tested only.
  A Playwright (real-browser) e2e would close the runtime gap. [Test/QA]
- **A live `--demo-scenario` matrix.** Beyond the single gate-failed scenario (QA-002), a small set of
  demo fixtures (gate-fail, needs-experimental, model-unavailable, slice-timeout) would make every
  error/empty state hands-on demoable and screenshot-testable. [QA]
- **Mobile is a real design surface, not just "stacked."** Even after the UX-004 sticky-CTA fix, the
  phone layout deserves a dedicated design pass (segmented nav, viewport sizing, gallery/settings on
  a phone) before mobile is a launch surface. [UI]
- **Material control single source of truth.** Stage 8.5 left material selection in the Export card;
  the reference put a material segmented control in the gate card too. Decide one home (don't ship
  two) — relevant when CadQuery/precision lands. [UI/Eng]
- **Re-orient / orientation control.** The viewport shows "Auto-oriented · plate-down" but there's no
  user re-orient. A real orientation control (and the reference's "change" affordance) is a future
  capability, not a Stage 8.5 promise. [UI/Eng]
- **CLI vs UI model policy.** ENG-006: the CLI `model_advisor` can still surface Qwen. Even after
  deprioritizing it, decide deliberately whether the CLI advisor is a power-user tool that may list
  alternatives or must mirror the UI's gemma4-only stance. [Eng]
- **Hosted-CR parity for the live (OrcaSlicer) tests.** The live-assembled tests run only via the
  local pre-push hook today; a clean-VM / hosted runner with the bundled binaries would make the live
  gate signal independent of one developer's machine. [Test]
- **Cloud-provider cache + secret lifetime.** ENG-005 bounds the cache now; longer term, consider not
  retaining the API key as a cache key at all (key by model; hold the secret only transiently). [Eng]
- **Readiness "compared to your past prints" depth.** The history store + comparison line are factual
  but shallow; a richer learning surface is a Stage-7-follow-on opportunity. [UI/Eng]
- **STEP/BREP + G-code export formats** arrive with the CadQuery engine (Stage 8) and the direct-print
  UI (Stage 10) — keep the honest "arrives later" framing until then. [UI]
