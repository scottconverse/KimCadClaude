# Prompt — harden the `/walkthrough` skill against missing first-run / zero states

> Paste this into a fresh session that can edit the walkthrough skill at
> `C:\Users\scott\.claude\skills\walkthrough\` (SKILL.md and `references/report-template.md`).

---

You are updating the `/walkthrough` skill so it can never again pass a product that is broken for
brand-new users.

## What went wrong (the incident this fixes)

The `/walkthrough` skill was run on KimCad (a local app whose core feature needs a local AI engine,
Ollama) and gave it a near-clean bill of health — **one Minor finding.** But it completely missed
the single worst problem in the product: a brand-new user with no Ollama installed hits a **dead
end** — the first-run wizard's "Set up your AI" step just tells them to go install Ollama themselves
and come back, and "Design it" is disabled. The product owner hit this the first time he installed
the app. The walkthrough never saw it.

**Root cause — two compounding failures:**

1. **It ran on an already-provisioned developer box.** Ollama was installed and running, the models
   were pulled, settings were configured, cloud was enabled. So the "AI not set up" / first-run /
   dependency-absent state was *never on screen*. The skill walked the warm happy path and reported
   it as healthy.
2. **The environment "isolation" silently failed and nobody checked.** The walkthrough used a
   `USERPROFILE` override intended to give a clean profile, but it did not actually take effect — the
   app read the real, fully-provisioned profile. The "clean" walkthrough was secretly a warm one, and
   no step verified the isolation held.

**The lesson:** a UI walkthrough must **construct and verify the true first-run / zero / dependency-
absent state** — not observe whatever convenient state the dev box happens to be in. The most
important user state (first launch, nothing set up) is exactly the one a developer's machine never
shows.

## Make these changes to the skill (in its own voice/structure)

**A. Mandatory zero-state / first-run pass.** Before or alongside the happy-path walk, the skill MUST
drive the product as if freshly installed on a clean machine: fresh user profile, external
dependencies NOT running (model server / DB / license / cloud creds absent), empty data stores,
first-run flags unset. Walk what a brand-new user sees — the onboarding/first-run flow, the
landing/empty states, and an attempt to use the core feature with nothing set up. Not optional; not
satisfied by "observing empty states if they happen to appear."

**B. Verify the environment is what you think it is — never assume.** Before trusting any
state-coverage claim, CONFIRM the preconditions actually hold: that the "clean" profile is genuinely
clean (assert the app wrote to the isolated location, not the real one), and that the intended
dependency state is real (probe it). If isolation can't be verified, the run is INVALID for first-run
findings. (KimCad's USERPROFILE override silently failed — the skill must check, e.g., that
`~/.kimcad` under the isolated home was actually created/used.)

**C. Provisioning matrix.** Enumerate the environment preconditions that change what the user sees,
and walk each combination that matters: {first-run vs returning} × {core dependency present vs
ABSENT} × {data empty vs populated} × {offline vs online}. A product with an external dependency (a
local model server, a database, an API key, a license) MUST be walked with that dependency ABSENT —
the absent case is the new-user reality, and it's where dead-ends live.

**D. Construct each rendered state — don't wait to stumble on it.** Strengthen the existing
"cover loading/empty/error/success/partial states": the auditor must deliberately PRODUCE each state
(point at a dead backend, clear the data store, stop the dependency, throttle the network), not merely
report whichever the happy path surfaced.

**E. State the dev-box-convenience trap explicitly.** Add a warning: a developer's machine is the
WORST place to judge first-run UX, because everything is already installed and configured. Treat an
already-provisioned environment as a DISQUALIFYING condition for first-run findings until it is reset
to a clean state.

**F. Report template additions.** In `references/report-template.md`, add (1) a required
"Zero-state / first-run" findings section, and (2) an "Environment provisioning — verified" attestation
that records exactly what was confirmed clean/absent and HOW it was verified — so a future reader can
see the cold state was actually exercised, not assumed.

After editing, re-read the skill end-to-end and confirm that a first-run dead-end like KimCad's could
not pass review again: the skill now forces a verified-clean cold pass and refuses to certify first-run
UX from a provisioned box.
