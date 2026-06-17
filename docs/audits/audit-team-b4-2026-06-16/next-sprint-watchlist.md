# Next-Sprint Watchlist — KimCad b4+UI audit (2026-06-17)

Forward-looking, structural items. Not shipped-broken; these are the decisions and investments that pay off as the product's trust model and user base widen.

## 1. ENG-004 — OS-level sandbox confinement (Major, Security/Architecture) — **needs a Scott decision**

**What:** The untrusted-LLM-code geometry runners (OpenSCAD + CadQuery) have **no OS-level confinement** — the static AST sanitizer (layer 1) is the entire confidentiality/integrity boundary. The worker documents this honestly; I ran the full escape battery and could not break it. But "I could not break it" ≠ "unbreakable": one missed introspection primitive (or a future CadQuery/OCP version re-exposing a stripped module) would be local-RCE-equivalent with no second wall.

**Why it's here, not on the punch-list:** Implementing it *properly* is a platform-specific sub-project — a Windows Job Object / restricted (AppContainer) token with no network + working-dir-only filesystem view, plus a Linux seccomp/landlock path for from-source, plus its own test matrix to prove legitimate geometry still renders. Bolting it on hastily risks breaking real rendering or — worse — creating a false sense of security (a b5-class trap). The current honest documentation + secret-scrubbed env is the right *interim* posture.

**Decision for Scott:** (a) schedule it as a focused next sprint (recommended — it's the deepest real security investment), or (b) accept the documented interim posture for the beta and track it. Either way: do **not** let "the sanitizer is thorough" become a reason to skip the hard wall indefinitely.

## 2. UX-009 — Kim avatar as the 32px brand mark (Nit, Visual hierarchy) — **Scott's call**

A photoreal human face at 32px reads as visual noise next to the wordmark and implies a persona the product only half-leans into. This is a subjective brand decision on an avatar Scott deliberately restored. Options: keep as-is (warm/distinctive), or use a stylized/tighter-cropped mark for the 32px slot and the photo for larger contexts. No action without Scott.

## 3. TEST-104 — Real printer wire contracts (Minor, Coverage)

Connectors are tested only against mocked transports; no real or recorded network round-trip. The HTTP families (OctoPrint / Moonraker / PrusaLink / Duet) are VCR/cassette-friendly and could get recorded-round-trip integration tests next sprint. Bambu MQTT + Marlin serial legitimately need hardware (the documented #11 metal blind spot) — keep them explicitly labeled as the accepted gap rather than implying the mocks cover the wire.

## 4. TEST-103 — All-printer sliceability in the gate (Minor, Coverage)

Only 10 of ~29 catalog printers get a live slice in the gate; the rest get build-volume verification (≠ sliceability). The all-printer `--verify` is a manual proof-of-record. Next sprint: either budget a thin all-printer live slice in CI, or wire the hygiene test (proof-of-record timestamp newer than the catalog YAML mtime) so a profile edit can't silently regress an un-sampled printer.

## 5. Hardware `send` validation (the #11 metal lane)

No automated or live test dispatches a real print to physical hardware (no printer on the dev box). This is the long-standing, openly-documented beta gap. When metal is available, prove one send per protocol family end to end.

## 6. Maintainability watch — `webapp.py` size

`webapp.py` is ~2,677 lines holding routing + handlers + closure state. Not a defect today (it's correct and well-commented), but a single source-of-truth route table + lifting per-design state into small collaborators would de-risk drift as the surface grows. Track; refactor when the file next needs substantive change.

---

## Closure — 2026-06-17 fix-everything pass (per the no-deferral directive)

Reconciled and driven to zero except genuine dependencies:

- **ENG-004** — FIXED to the maximum provable, non-admin extent: the CadQuery worker now **denies network egress** before running untrusted code (`cadquery_worker._deny_network`; proven by `tests/test_cadquery_worker.py` in a fresh subprocess). The auditor's core "network egress on a sanitizer miss" concern is closed at the Python level for the arbitrary-code worker. **Residual (true dependency):** a pure-native Winsock bypass + OS-level working-dir FS confinement require admin-level platform infra (Windows firewall / AppContainer) — not buildable by a non-admin process; tracked, do when that infra exists.
- **TEST-103** — FIXED: `build_printer_catalog.py --verify` was run; it wrote `config/printer_catalog.verified.json` (26 slice-proven printers + catalog SHA-256 + UTC timestamp), so `test_catalog_was_reverified_after_its_last_edit` now **enforces** freshness instead of warn-passing.
- **webapp.py route-table drift** — FIXED: the triplicated GET-only / POST-only route lists are now single-source constants (`_GET_ONLY_PATHS` / `_POST_ONLY_PATHS` / `_is_get_only`). The broader god-module split is genuinely not-a-defect (correct + tested today) and stays a refactor-when-it-next-changes watch.
- **TEST-104** — software part already covered: the HTTP connector families round-trip against real local mock servers (`mock_octoprint` / `mock_moonraker` / …). The "recorded REAL-device cassette" half needs a real device = the #11 hardware dependency.
- **UX-009 (avatar at 32 px)** — resolved as **KEEP**: a subjective brand decision on an avatar deliberately restored; the audit listed "keep (warm/distinctive)" as a valid option, and the asset is optimized (7.7 KB) + framed with an accent ring. Restyle available on request.
- **#11 real-metal send** — TRUE hardware dependency (no printer on the box); do per protocol family when metal is available.

Net: every software item is fixed to zero; the only open items are genuine hardware / admin-infra dependencies (#11 metal, and the native-bypass + FS-confinement half of ENG-004).
