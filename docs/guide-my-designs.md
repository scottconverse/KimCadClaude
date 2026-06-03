# Saving your work & the "My Designs" library

*Stage 8.5 Slice 1 — implemented on branch `stage-8.5-usability` (not yet merged/tagged).*

KimCad keeps your designs for you. You don't have to remember to save, and closing the tab or
refreshing the page no longer loses your part.

## Your work is saved automatically

The moment a part finishes building, KimCad saves it to a local **My Designs** library and gives the
page its own address (the URL changes to `#/design/…`). A small **"Saving… → Saved · My Designs"**
note in the top bar tells you it happened. If a save can't complete for a moment it shows
"Couldn't save — retrying" and tries again on its own — your on-screen part is never lost in the
meantime.

Adjusting a part's sliders re-saves the same entry (it won't pile up duplicates), so the version in
your library always matches what you last saw.

## Where your designs live

Everything is stored **on your own computer**, under:

```
~/.kimcad/designs/
```

Nothing is uploaded anywhere. Each design is a small folder with its details, its 3D mesh, and a
thumbnail. The library keeps your most recent designs (older ones beyond a generous limit are
dropped automatically).

## The My Designs library

Click **My Designs** in the top bar to open your gallery. Each card shows the part's thumbnail,
name, and date, with actions:

- **Open** — click the thumbnail or name to reopen the design, with its live sliders restored.
- **Rename** — give it a clearer name (press Enter to keep, Esc to cancel).
- **Duplicate** — make a copy to branch from; the copy appears as the newest item.
- **Export (.kimcad)** — download a portable backup file (see below).
- **Delete** — removes it. This is a two-step click (it asks "Delete?" first) so you can't lose a
  design to a stray tap.

Use the **search** box to filter by name and the **sort** menu to order by newest, oldest, or name.

## Moving a design between machines: export & import

- **Export** hands you a `.kimcad` file — a backup of one design. It is **not** a printable STL or
  3MF; it's KimCad's own file for saving or sharing a design.
- **Import** (the button at the top of My Designs) loads a `.kimcad` file back in as a new design,
  alongside whatever you already have. The maximum import size is 32 MB.

Importing only ever reads the design's own three files, so a `.kimcad` from someone else can't write
anything elsewhere on your computer.

## Frequently asked

**Do I need to click Save?** No. Saving is automatic. The top-bar note is just reassurance.

**Is my work sent to the cloud?** No. The library is entirely local, under `~/.kimcad/designs/`.

**I refreshed / closed the tab — is my part gone?** No. Reopen it from My Designs, or just revisit
the same page address; the part and its sliders come back.

**What's a `.kimcad` file?** KimCad's portable backup of a single design — for moving it to another
machine or keeping a copy. Re-import it with the Import button. (For a *printable* file, use the
model / G-code download in the workspace instead.)
