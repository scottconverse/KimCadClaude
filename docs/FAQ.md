# KimCad FAQ

Quick answers to the questions beta users actually ask. Deeper detail lives in the
[User Manual](USER-MANUAL.md); install steps in the [install guide](install-guide.md);
problems in [troubleshooting](troubleshooting.md).

### 1. Windows showed a scary blue "Windows protected your PC" screen. Is this safe?

Yes — that's SmartScreen reacting to an **unsigned beta** (we don't have a code-signing
certificate yet; signing is planned). Click **More info**, confirm the file is the KimCad
installer you downloaded ("Unknown publisher" is expected), then **Run anyway**. Only
download the installer from the official KimCad GitHub Releases page — and if you want
certainty, verify the SHA-256 checksum published alongside it. KimCad runs entirely on your
computer; the installer uploads nothing.

### 2. Why is KimCad local-first? Why not just use a cloud AI?

Because your designs are yours. The whole pipeline — the AI, the CAD engines, the
printability check, the slicer — runs on your machine; nothing you make leaves it. No
account, no subscription, and it keeps working with the network unplugged. Cloud is
available strictly as an **opt-in** for hard prompts (see Q9).

### 3. Which AI model does KimCad use?

Two local models via [Ollama](https://ollama.com): a chat model (`qwen2.5:7b`) that turns
your words into a structured design plan, and a small vision model that reads photos and
sketches. The chat model won a measured bake-off against alternatives — KimCad ships the
benchmark harness (`kimcad bench`, `kimcad bakeoff`) so that decision stays re-checkable
rather than folklore.

### 4. The first setup is downloading something huge. What and why?

The two local models total roughly **7.7 GB** as a one-time download — the chat/planner model
(~4.7 GB) plus the vision model (~3 GB) — the price of a capable AI that runs entirely on your
machine. KimCad also sets up its own AI **engine** on first run: if Ollama is already installed
it just uses it, otherwise it downloads Ollama's official **portable** build (~**1.4 GB**, a
separate one-time download — no install, no admin) into its own data folder. The **Set up
KimCad's AI** button does both, in one flow, with a live progress bar; your designs afterward
need no network at all. (Free-disk recommendation is higher — see the install guide — because
that headroom covers both downloads with room to spare.)

### 5. How long does a design take?

On the reference hardware (a recent CPU, no graphics card needed): typically **one to two
minutes** for the AI planning step, then seconds for the geometry. Template parts re-render
from the sliders **instantly** — no AI call. A slow first design usually means the model is
still loading into memory; the second is faster.

### 6. What makes a good prompt?

Name the object and give real millimeters for the dimensions you care about: *"a wall hook,
60 mm tall back plate, reaches 35 mm out"* beats *"a hook"*. You don't have to be complete —
KimCad asks at most one clarifying question, picks sensible defaults for the rest, and
every dimension stays adjustable on the sliders afterward.

### 7. Where do my files live?

Saved designs (**My Designs**), settings, and the learning history live in `~/.kimcad`
(your user folder — nothing in the install directory, nothing in any cloud). Downloads
(`.stl`, `.step`, `.gcode.3mf`) go wherever your browser saves them.

### 8. What does the printability check actually check?

Before a part can be sliced: the mesh is **watertight** (printable at all), the built size
**matches the plan** on every axis, the part **fits your printer's build volume** (verified
against the same machine profile the slicer uses), wall thicknesses suit the material, and
the PrintProof3D engine adds an independent validation pass. A failed part is never
sliceable or sendable — the report tells you what's wrong and the sliders usually fix it.

### 9. Does anything ever go to the cloud?

Only if you turn it on. **Cloud acceleration** (Settings) is off by default; enabling it
sends your *prompt* to a model you choose via OpenRouter, with your own key — stored in the
Windows credential store, shown only masked. Photos and sketches are **always read
locally** and are never uploaded, full stop. The UI labels where work ran.

### 10. What's the readiness score on a finished part?

Smart Mesh — a local learning layer on top of the printability check. It scores the part,
lists risks and recommendations, and compares against your own history of similar parts.
Low confidence early on just means *not much history yet* (it's per-machine and grows as
you print); it is not a defect in the part.

### 11. Can KimCad start a print on its own?

No, by design. Slicing requires your explicit confirmation, sending requires another one,
and a part that failed the printability check can't be sent at all. There is no auto-start
anywhere in KimCad, and there never will be.

### 12. Which printers work?

Three reference printers (Bambu Lab P2S, Bambu Lab A1, Elegoo Neptune 4 Max) are wired
end-to-end with slicing **proven in CI**, and the installer bundles OrcaSlicer's full
profile library — **~65 brands, 1,400+ machines** — with picker support for the rest of
that library in active development. Direct send works over **your LAN, no printer cloud**:
Bambu (native), OctoPrint, Moonraker/Klipper, PrusaLink, Duet/RepRapFirmware, and Marlin
(Ender-class, over USB serial or a network bridge). No physical print is certified
yet — that's exactly what this beta exists to prove; always watch first prints.

### 13. Why LAN-only for Bambu? Where's cloud mode?

Deliberate. Cloud-mandated printing is one of the most disliked aspects of that ecosystem;
KimCad's point is giving you back **direct control of your own printer**. LAN mode is the
supported path, permanently.

### 14. What's the `.STEP` download, and why don't I see it?

`.STEP` is the editable, precision CAD model — open it in Fusion 360, FreeCAD, or
SolidWorks and keep modeling. It appears on standard (template-built) parts once the
optional **CAD export engine** is installed: *Settings → Editable CAD export* walks you
through the one-time setup (a single `pip install` in a terminal — it's the one power-user
feature that asks for one). KimCad builds the STEP from its own trusted code, never from
AI-generated code, and the first download takes a few seconds.

### 15. What's the "experimental direct shape generator"?

For requests no template covers, the local AI can write the 3D geometry directly. It's off
by default, clearly labeled, sandboxed, and its output still has to pass the full
printability check — but the results can be rough, which is why it's opt-in per the toggle
in Settings rather than silent.

### 16. The part isn't what I meant. What now?

In order of effort: drag the **sliders** (instant); **say what's wrong** in the refine box
("make the plate wider", "the holes should be 5 mm") — it keeps your design and applies the
change; or start over with a more specific prompt (Q6). Nothing you do can wreck a saved
design — re-renders are deterministic and versioned.

### 17. Something's not running — the AI, a tool, the photo reader.

The UI tells you which piece is down and how to fix it. If the AI engine is down, the wizard's
**Set up KimCad's AI** / **Check again** button restarts (or re-provisions) it — KimCad runs its
own engine, so there's nothing for you to start by hand; a missing vision model gets re-fetched
the same way. The longer list — port conflicts, model pulls, tool paths, logs — is in
[troubleshooting](troubleshooting.md). Re-running the setup wizard (Settings) repairs most
first-run states.

### 18. Is this actually ready to use?

It's an honest beta. Software-complete and heavily gated: ~1,000 backend tests plus a fully
tested UI run on every push, the pipeline slices end-to-end for the three reference
printers, and the installer is verified on the real installed tree. What's *not* proven yet
is metal: no physical print has been certified, printer connections are validated against
conformance mocks, and the installer is unsigned. Treat it accordingly — and tell us what
you find in [Discussions](../../discussions); that's what the beta is for.

### 19. Do I have to describe everything from scratch? Is there a parts library?

There is. KimCad ships a **library of 86 ready-made part families** you can browse
instead of typing a description — boxes, hooks, brackets, picture frames, trinket dishes,
plant pots, ornaments, candle holders, display stands, and everyday hardware like washers,
spacers, and standoffs. Open the library from the start page, search for what you want
(*"tray"*, *"hook"*, *"planter"*), pick a card, and KimCad designs it on the spot — then you
adjust it with the sliders like any other part. It's a starting shelf, not a limit: describing
a part in your own words still works, and KimCad can design things the library doesn't list.
The full catalog is in the [part-library reference](templates.md).

### 20. Some library parts have a "Verify before use" tag. What does that mean?

It means the part has to **fit something in the real world** — a screw, a glass tube, a phone,
a Gridfinity drawer, a monitor's mounting holes — or carry a load, and only you can confirm
that fit. It is *not* a warning that the part is broken: the geometry is just as real and just
as checked (against its exact measured size) as any other part. KimCad labels these parts
honestly so it never overpromises. A printed "nut" or "bolt", for instance, has a smooth hole
and shaft rather than real cut threads; a "VESA plate" gives you the standard hole *pattern* to
line up with your device. When you see the tag, measure twice — or print a quick test — before
you rely on the fit. Parts without the tag are exactly what you set, with nothing extra to
check. (Internally these are the *baseline* tier; untagged parts are *benchmarked*.)
