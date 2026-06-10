# Stage 10 gate — next-sprint watchlist (Stage 11+)

1. **A real connections Settings surface.** Stage 10's root UX finding: the send flow's
   management venue doesn't exist — config.yaml + env vars are the real venue, reachable
   only outside the app. Stage 11 (the non-technical-user installer stage) is where a
   minimal in-app connections card (IP/serial fields + access-code env instructions +
   per-piece status from /api/connector-status) earns its keep. *(UI/UX + Engineering)*

2. **Hardware-contact protocol for the Bambu connector.** The remediated edges (busy
   fail-closed, defensive disconnect, auth mapping, nozzle-unknown) are mock-proven only.
   First contact at Kim's: a scripted checklist — status read, deliberate wrong access code
   (expect `auth`), a real small send, a busy-refusal attempt during it, session-churn watch
   (firmware connection limit). Budget an hour before the first real print. *(QA)*

3. **The G-code viewer disposition.** The Stage 8.5-era promise is resolved at this tag as
   explicitly deferred-not-dropped. If beta users ask for layer preview, it's a Stage 12+
   candidate; the CHANGELOG entry records the deferral. *(Product)*

4. **`JOB` singleton vs multi-instance.** The injection seam lands this sprint; if KimCad
   ever runs multiple web servers in one process (unlikely for the beta), revisit pull-job
   scoping per instance. *(Engineering)*

5. **Installer disk math (carried from Stage 9 watchlist, now closer).** The Stage 11
   bundled installer must free-space-check before the two model pulls — model_pull.py's
   pre-check is reusable as-is (it honors OLLAMA_MODELS). *(Engineering)*

6. **Frontend async-lifecycle test discipline.** The recurring weak class (TEST-1001 and
   Stage 9's TEST-008 sibling): fake-timer tests must install timers BEFORE the component
   schedules them. Worth a frontend/README testing note so the pattern doesn't regress.
   *(Test)*

7. **The remaining cloud connector paths.** ROADMAP Stage 10 says "the remaining cloud
   paths as feasible" — Bambu cloud mode wasn't built (LAN mode only, deliberate: simpler,
   more private, no account dependency). The EXIT MET block records that disposition; if a
   beta user can't use LAN mode, revisit. *(Product)*
