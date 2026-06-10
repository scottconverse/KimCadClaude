# Settings, and the cloud opt-in

Everything in **Settings** (the gear in the top bar) is local preference — KimCad works
fully without touching any of it. This guide explains what each section does, and exactly
what the optional cloud acceleration sends and stores.

## Your printer and material

The defaults every new design is checked and sliced against. Changing them here changes
the build-volume check, the wall-thickness rule, and which slicing profile is used.
A printer marked "no slicer profile yet" can still be designed for — it just can't
produce a print file yet.

## The AI model

A health readout, not a menu: KimCad runs one tested local model (`gemma4:e4b` via
Ollama). Settings shows whether it's running and pulled, with a re-check button — the
same status the start page and setup wizard show.

## Cloud acceleration (optional — off by default)

KimCad's local AI does everything. Turning on cloud acceleration lets KimCad *also* send
design requests to a bigger model through OpenRouter, which can help with unusual parts —
at a privacy cost you should make knowingly:

- **What it sends, when enabled and configured:** the text of your design request (your
  prompt and the conversation around it). **Never your photo** — the photo on-ramp always
  stays local. Nothing is sent until you've turned the toggle on, saved a key, *and*
  chosen a cloud model.
- **What it costs:** OpenRouter bills your key per request. KimCad doesn't meter or cap it.
- **Where your key lives:** in **Windows Credential Manager** — your computer's secure
  credential store — not in a plain file. (If that store isn't available, KimCad falls
  back to its settings file and *tells you so* right under the key field.) The key is
  shown only masked after saving, and "Reset all settings" removes it from the credential
  store too.
- **Turning it off:** flip the toggle; local keeps working exactly as before. Clearing
  the key field deletes the stored key.

## The experimental generator

Off by default. When a part doesn't match any of KimCad's built-in shape families, this
lets the AI write raw CAD code for it — more flexible, less predictable. Every result
still goes through the same printability checks; nothing skips the gate.

## Reset

"Reset all settings" returns everything above to fresh-install defaults and deletes the
saved cloud key (including from the credential store). Your saved designs are not touched
— they live in My Designs, not here.
