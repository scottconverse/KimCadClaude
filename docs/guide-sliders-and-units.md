# Live sliders & units — adjusting a part after it's designed

*Stage 5 — shipped; merged to `main` and tagged `stage-5`.*

When KimCad builds a part from one of its parametric **templates** (a box, tray, enclosure, tube,
hook, cable clip, or drawer divider — these are just examples from one of KimCad's **86 template
families**; see the [catalog](templates.md)), you don't have to re-describe it to change its size.
The part comes with **live sliders** — drag one and the part re-renders right there in the viewport.

## Adjusting with the sliders

Each adjustable dimension (width, depth, height, wall thickness, …) gets its own slider in the
right-hand **Parameters** panel.

- **Drag a slider** and the part rebuilds in well under a second. This is deterministic and runs
  entirely on your machine — **no AI model is called** for a slider change, so it's instant and
  free even on a CPU-only box. While it rebuilds you'll see a brief "Re-rendering…" cue.
- The viewport's **W / D / H dimension pills** update as you drag, so you can read the part's real
  size as you change it.
- Every re-render re-runs the **printability gate** and refreshes the readiness card, so the
  verdict you see always matches the shape currently on screen.

## Typing an exact value

Dragging is good for exploring; for a precise number, **click the value** next to a slider. It
turns into a text field — type the exact size and press **Enter** (or click away) to apply, or
**Esc** to cancel. Out-of-range entries are clamped to the slider's limits and the field tells you
the valid range.

## Switching between millimetres and inches

Use the **mm / in** toggle (in the Parameters panel and in Settings) to read and enter sizes in
either unit. Toggling converts every slider value, the numeric fields, and the dimension table at
once, and your choice is remembered between sessions. Internally the part is always built in mm —
inches are just for display and entry — so switching units never changes the part.

## What if a part has no sliders?

Sliders appear only for **template-backed** parts (the deterministic families above). A part built
by the experimental free-form generator has no fixed parameter set, so it shows no sliders — to
change it, describe the change in the chat instead (e.g. "make it 10 mm taller") and KimCad
re-designs it.

## A note on size limits

The sliders stop at the largest size that reliably **slices** for the reference printers, which is
a bit smaller than the bed's physical dimensions — the slicer reserves clearance around the plate
edges. This keeps a part you can build on screen, rather than one that passes the on-screen checks
but then can't be sliced.

See also: [`guide-my-designs.md`](guide-my-designs.md) for saving and reopening the parts you make.
