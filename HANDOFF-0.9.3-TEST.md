# Resume prompt — KimCad 0.9.3 awaiting clean-machine tester verdict

**Date paused:** 2026-06-18 · **Reason:** Anthropic Codex update reinstall.

## What's already shipped (live, NOT to redo)

- **`main` HEAD = `7f8e9ee`** — all Zen Design World branding work merged.
- **`tester` branch HEAD = `0264172`** — directive-009 published.
- **Tag `v0.9.3`** — pushed, points at `7f8e9ee`.
- **GitHub release `v0.9.3`** — published as **PRE-RELEASE**:
  https://github.com/scottconverse/KimCadClaude/releases/tag/v0.9.3
  - Asset: `KimCad-Setup-0.9.3.exe`
  - Size: `204,050,711` bytes
  - SHA-256: `f2c97eceb2bdd624fff1d2c861ea22fd176cbac7acb351e8da41587ee0dd25b8`
  - Source commit: `7f8e9ee`
- **Tester directive**: [tester/directive-009-clean-install-0.9.3.md](https://github.com/scottconverse/KimCadClaude/blob/tester/tester/directive-009-clean-install-0.9.3.md)
  - NONCE `KCT-009-20260618-093`
  - Phase 0 wipes EVERY remnant including LLM artifacts (Scott emphatically required).
  - Phase 4 is the Kim Everywhere survival checklist (13 surfaces).

## What I'm waiting on

The tester to push a **`TESTER d009 COMPLETE`** commit to `origin/tester` with:
- `tester/reports/report-009.md` (verdict: SHIP / SHIP-with-Minor / HOLD)
- `tester/evidence/009/*` (screenshots, hashes, registry dumps, etc.)

## On resume — first action

```bash
cd /c/Users/scott/Desktop/Code/kimcadclaude
git fetch origin tester
git log origin/tester --oneline -3   # look for "TESTER d009 COMPLETE"
```

Or via GitHub API:
```bash
gh api repos/scottconverse/KimCadClaude/commits?sha=tester --jq '.[0:3] | .[].commit.message'
```

### If d009 report = SHIP (clean: 0/0/0/0/0 across the branding checklist + functional re-prove)

1. `gh release edit v0.9.3 --prerelease=false` — flip from pre-release to Latest.
   **NO version change. Same tag. Same artifact. Same SHA. Only the release status flips.**
2. Read the report, link Scott to it, confirm the flip.
3. Memory entry + close the sprint.

### If d009 report = SHIP-with-Minor

1. Read each Minor; ask Scott which to fix in-place vs. ship and follow-up.
2. For in-place fixes: branch off main → fix → rebuild installer → bump SHA in directive-009 → push tester directive-009b → wait for re-verify → flip release.

### If d009 report = HOLD (Blocker or Critical found)

1. Read the report carefully. Don't rationalize a downgrade — Scott's "no false greens" rule applies.
2. Fix per the directive's blast radius. Likely a new tester pass (d010) before flipping.
3. **Do NOT flip v0.9.3 to Latest until tester signs off.**

## Standing rules in force

- **DOCS-ONLY pushes ALWAYS use `--no-verify`** ([[respect-time-and-resources]] — second-strike rule, 2026-06-18). The 16-min code gate is for code; using it on docs/tags/PDFs is forbidden.
- **No version changes during the 0.9.3 cycle.** Scott set the rule: "no more version changes until we get THIS version finished." 0.9.3 is the number. If a Minor fix lands, it's still 0.9.3 (re-issue the artifact at the same version, bump only the SHA in the directive).
- **Never push without Scott's explicit OK** on the specific change ([[stop-immediately-never-push-unapproved]]).
- **Kim's face is the brand mark** ([[kimcad-is-for-kim]]). Any tester finding about the branding gets fixed, not rationalized away.

## Loose ends I might need to clean later

- The `dist/KimCad-Setup-0.9.3.exe` artifact is gitignored but lives on disk — keep until release is promoted.
- `/tmp/directive-009-final.md` — backup of the filled-in directive. Safe to delete.
- The old `HANDOFF-BRANDING-RESUME.md` is now superseded by this file.
