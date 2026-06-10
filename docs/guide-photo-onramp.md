# Starting a design from a photo

Sometimes the easiest way to describe a part is to show it. The photo on-ramp reads a
picture of an object and turns it into a rough written description — sizes estimated,
shape named — that you can edit before KimCad designs anything.

## The promise first

**Your photo never leaves your computer.** It's read by a small local vision model
(`qwen2.5vl:3b`, running in the same Ollama as the design model), on your machine, even
if you've turned on cloud acceleration in Settings — the photo path always stays local,
by design. The photo isn't saved anywhere either: once it's been read (or you cancel),
it's gone. Only the *text* description you approve goes on to the design step.

## How to use it

1. On the start page, choose **describe with a photo** (next to the text box).
2. Pick a photo. Clear, side-on shots of a single object work best; a ruler or a known
   object (a coin, a battery) in frame helps the size guess.
3. KimCad reads it and shows you a **draft description** — plain words, like
   *"a cylindrical cup about 80 mm tall and 70 mm across."*
4. **Edit it.** The sizes are estimates; fix anything that's off. This draft is just a
   head start on the same text box you'd have typed into anyway.
5. Send it. From here it's a normal design: preview, refine, check, download.

## What it's good at — and not

Good: simple functional shapes (brackets, holders, containers, clips) where you want a
starting point faster than typing. Not good: precise measurement (it estimates), complex
assemblies, or anything where exact dimensions matter more than overall shape — type
those numbers in yourself during the edit step.

## If it returns nothing

An empty or failed read usually means an **outdated Ollama** — older builds have a bug
that makes the vision read come back blank. Update Ollama from
[ollama.com/download](https://ollama.com/download) and try again. If your local AI isn't
running at all, KimCad says so (it never blames your photo for a stopped server). More in
[troubleshooting](troubleshooting.md).
