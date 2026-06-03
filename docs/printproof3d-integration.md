# PrintProof3D integration (Stage 7)

PrintProof3D is a separate, MIT-licensed Rust **validation engine** (the owner's project). KimCad
uses it — when it's present — to add deeper geometric / printability validation to the **Smart Mesh
readiness** report. KimCad does **not** ship or depend on it: the engine is entirely optional, and
when it isn't configured Smart Mesh falls back to KimCad's own Printability Gate (honestly, at lower
confidence). Nothing about the core pipeline changes whether the engine is there or not.

## How it's wired — arm's length, never linked

KimCad runs PrintProof3D as a **subprocess**, never as a linked library:

- `printproof3d.py` builds an argv list and runs the binary with no shell:
  `printproof3d validate-model --model <mesh.stl> --printer <printer.json> --material <material.json> -o <report.json>`
- KimCad generates the engine's printer/material profile JSON **from its own config** (KimCad's
  `Printer`/`Material`), so you don't maintain a second set of profiles.
- The mesh handed to the engine is the **final hardened mesh, bed-positioned** (min-corner at the
  bed origin) so the engine's bounds checks measure from `[0, build]` rather than false-flagging a
  centered part.
- Success is gated on the **parsed report file**, not the process exit code — PrintProof3D exits
  non-zero on a *fail verdict*, which is a normal result, not a crash.

This boundary is deliberate: an external, in-development engine can crash, time out, or emit a
garbled report, and none of that may break a KimCad build. Every failure mode degrades to "no
engine" (`None`) and Smart Mesh proceeds on the gate alone. `validate_model` **never raises**.

## Enabling it

The engine is **off by default** — the path is configured but the binary isn't fetched, so KimCad
resolves it to "not present" and degrades.

1. **Build the engine** from its repository (Rust toolchain required):
   ```
   cargo build --release
   ```
   This produces the `printproof3d` binary under that repo's `target/release/`.
2. **Point KimCad at it.** In `config/local.yaml` (per-machine, gitignored), set:
   ```yaml
   binaries:
     printproof3d: C:\path\to\PrintProof3D\target\release\printproof3d.exe
   ```
   A relative path resolves against the KimCad project root; an absolute path is used as-is. The
   default in `config/default.yaml` is `tools/printproof3d/printproof3d.exe` — drop a built binary
   there and it's picked up with no config change.
3. That's it. `Config.printproof3d_binary()` returns the path only when the file actually exists, so
   a configured-but-not-yet-built path still degrades cleanly rather than erroring.

When the engine is configured and present, the readiness card's confidence rises to **High** and its
attribution reads **"PrintProof3D validation engine"**; without it, the card reads **Medium** /
**"KimCad printability gate."** The card never claims the engine ran when it didn't.

## The report contract KimCad expects

KimCad parses a `ValidationReport` JSON with this shape (it tolerates extra fields and skips
malformed ones):

```jsonc
{
  "status": "pass" | "warning" | "fail",      // required; anything else → the report is ignored
  "confidence_level": "high",                  // free-form string (optional)
  "issues": [                                   // optional; a non-list is treated as empty
    {
      "id": "OVERHANG_UNSUPPORTED",            // the engine's error class
      "severity": "blocker|critical|major|minor|nit",  // an unknown severity → the issue is skipped
      "message": "A 55° overhang has no support.",
      "suggested_fixes": ["Add supports under the overhang."],  // optional; non-list → empty
      "location": { "region": "overhang" }      // optional
    }
  ]
}
```

PrintProof3D severities map onto the readiness score (a penalty per issue) and the card's risk list;
the overall `status` is folded into the verdict tone (the card is never more optimistic than the
engine's own status).

## Scope today

PrintProof3D is **advisory** in Stage 7: the readiness card surfaces its findings, but KimCad's own
deterministic Printability Gate remains the **slice authority** (a gate-failed part is not sliced; a
gate-passed part is sliceable even if the engine raised an advisory concern). Folding an engine
`fail` into the slice gate — so a serious engine-only defect blocks slicing — is a deliberate
follow-up, gated behind the engine being enabled by default. Until then, enabling the engine only
*adds* information; it never changes what slices.

## Privacy

The engine runs locally as a subprocess; nothing about your mesh, prompt, or profiles leaves the
machine. The Smart Mesh learning store it feeds (`~/.kimcad/history.json`) is likewise local-first
and coarse (no geometry, no prompt).
