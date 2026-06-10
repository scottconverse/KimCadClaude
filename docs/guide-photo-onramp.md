# Starting a design from a photo or a sketch

Sometimes the easiest way to describe a part is to show it. KimCad has two image
on-ramps, side by side next to the text box:

- **Describe with a photo** — reads a picture of an object into a rough written
  description, sizes *estimated*, shape named.
- **Start from a sketch** — reads a drawing with written dimensions, and takes those
  dimensions *as written*, not estimated.

Either way you get an editable draft description before KimCad designs anything — the
image is a head start on the same text box you'd have typed into anyway.

## The promise first

**Your photo or sketch never leaves your computer.** It's read by a small local vision
model (`qwen2.5vl:3b`, running in the same Ollama as the design model), on your machine,
even if you've turned on cloud acceleration in Settings — the image path always stays
local, by design. The image isn't saved anywhere either: once it's been read (or you
cancel), it's gone. Only the *text* description you approve goes on to the design step.

## How to use it

1. On the start page (or under the refine box in the workspace), choose **Describe with
   a photo** or **Start from a sketch**. You can click to pick a file or drop an image
   onto the button.
2. Pick your image (PNG or JPEG, up to 12 MB).
3. KimCad reads it and shows you a **draft description** — plain words, like
   *"a cylindrical cup about 80 mm tall and 70 mm across."*
4. **Edit it**, then send it. From here it's a normal design: preview, refine, check,
   download.

A slow read can be cancelled at any time — nothing is submitted until you choose
**Use this as a starting point**.

## Photos vs. sketches

**A photo can't tell us scale**, so every size in a photo's draft is an estimate. Clear,
side-on shots of a single object work best; a ruler or a known object (a coin, a battery)
in frame helps the size guess. Fix any size that's off in the edit step.

**A sketch carries its own dimensions.** Write the sizes on the drawing — "80 mm", "40 x
20 x 10 mm" — and they're read literally into the draft. A good sketch is one part per
page, dark lines on a light background, with the dimensions written clearly (units
included). Check the numbers came through in the draft before you continue; whatever the
draft says is what KimCad designs to.

## What it's good at — and not

Good: simple functional shapes (brackets, holders, containers, clips) where you want a
starting point faster than typing. Not good: precise measurement from a *photo* (it
estimates — a dimensioned sketch is the better tool for exact sizes), complex assemblies,
or anything where the overall shape can't be named in a sentence or two.

## If it returns nothing

An empty or failed read usually means an **outdated Ollama** — older builds have a bug
that makes the vision read come back blank. Update Ollama from
[ollama.com/download](https://ollama.com/download) and try again. For a sketch, also
check the dimensions are *written* on it — a shape with no labels reads into a shape with
no sizes. If your local AI isn't running at all, or the vision model isn't downloaded
yet, KimCad says so (it never blames your image for a setup problem). More in
[troubleshooting](troubleshooting.md).
