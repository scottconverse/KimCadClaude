# In-App Branding — ready-to-apply plan (review first, then we do it together)
**Branch:** `kim-branding-overhaul` · **Status:** assets staged, NOT applied to app source.

I deliberately did **not** edit the shipped app or rebuild the installer overnight — those
surfaces touch the server, the build, and the installer packaging, and you asked to review with
a cool head. Everything below is specified to the file + line so tomorrow is mechanical. All the
image assets are already made in `docs/redesign/assets/`.

The audit found Kim is present in exactly two places (top-bar logo + chat avatars) and **absent
from every OS-level surface.** These are the fixes, by severity.

---

## 🔴 Critical 1 — Favicon (browser tab + WebView2 window chrome are blank)
**Today:** `src/kimcad/webapp.py:938-942` intercepts `/favicon.ico` and returns a `204 No Content`
on purpose ("the SPA doesn't ship a brand asset yet").
**Change:**
1. Add `frontend/public/kim-favicon.png` (use `docs/redesign/assets/kim-96.png`) and
   `frontend/public/favicon.ico` (use `docs/redesign/assets/kim.ico`). Vite copies `public/` to the
   build root, so `kimcad web` will serve them.
2. In `frontend/index.html` `<head>` add:
   `<link rel="icon" type="image/png" sizes="96x96" href="/kim-favicon.png">`
   `<link rel="apple-touch-icon" href="/kim-favicon.png">`
3. In `src/kimcad/webapp.py` replace the 204 branch: serve `WEB_DIR / "favicon.ico"` (200,
   `image/x-icon`) if it exists, else keep the 204. (WebView2 requests `/favicon.ico` for the
   window chrome, so the file route matters even with the `<link>` tag.)
4. `npm --prefix frontend run build`; verify the browser tab + app window show Kim.

## 🔴 Critical 2 — Installer .exe + desktop + Start-menu icon (currently the Python snake)
**Today:** `installer/kimcad.iss` has no `SetupIconFile`; `[Icons]` shortcuts point at `pythonw.exe`
with no `IconFilename`.
**Change:** add `kim.ico` (from `docs/redesign/assets/kim.ico`) to the installer assets, then:
- `[Setup]`: `SetupIconFile=<path>\kim.ico` and `UninstallDisplayIcon={app}\...\kim.ico`
- both `[Icons]` entries: `IconFilename: "{app}\...\kim.ico"`
- **Requires an installer rebuild** to verify the .exe, desktop, and Start-menu icons. (This is the
  heavy/reviewable step — best done with you, on a real build.)

## 🟠 Major 3 — Native app window (title bar / taskbar / Alt-Tab)
**Today:** `src/kimcad/shell.py:124` `webview.create_window(...)` passes no icon.
**Change:** ship `kim.ico` inside the package (e.g. `src/kimcad/web/kim.ico`) and pass it to the
window (pywebview supports an icon via the window/WebView2). Verify the title-bar + taskbar icon.

## 🟠 Major 4 — First-run "Welcome to KimCad" shows no Kim
**Today:** `frontend/src/components/FirstRunWizard.tsx:249` rail shows only the text wordmark; the
Welcome step (step 0, ~line 274) has no avatar. The single best humanizing moment, missed.
**Change (isolated, additive, low-risk — a good first one to do together):**
- `import kimAvatar from '../assets/kim-avatar.png'`
- In `.kc-wiz-brand` (rail) put a round `<img src={kimAvatar} alt="Kim" class="kc-wiz-avatar">`
  before the wordmark.
- In the Welcome step, add a larger round avatar (~84px) above the `<h1>` so Kim greets the user.
- Add `.kc-wiz-avatar{border-radius:50%;box-shadow:0 0 0 1.5px var(--kc-hair-strong)}` to styles.css.

## 🟡 Minor 5 — In-app empty/landing state has Kim's voice but no face
`frontend/src/components/Landing.tsx:110-209` speaks in first person with no avatar. Add a round Kim
mark near the hero headline.

## 🟡 Minor 6 — Avatar accessibility
`kc-ava` / `kc-logo` are CSS background images on `aria-hidden` spans (styles.css:224, 2486). Where
Kim identifies the assistant, use a real `<img alt="Kim">` (or an accessible name) so screen-reader
users perceive the speaker and the mark survives high-contrast/print.

## Asset upgrade (do alongside the above)
The app avatar is **64×64px** (`frontend/src/assets/kim-avatar.png`) — soft if shown large. Replace
it with a **256px** crop from the 1254px master (`docs/redesign/assets/kim-avatar.png`), which
sharpens the logo, chat avatar, and the new wizard avatar at once for ~35KB.

---

### Suggested order tomorrow
1. Asset upgrade (256px) → 2. Welcome Kim face (#4, safe, verify in demo) → 3. Favicon (#1, verify
tab) → 4. Empty-state + a11y (#5/#6) → 5. Window icon (#3) → 6. Installer icon (#2, rebuild + verify)
→ rebuild SPA, run the gate, and only then decide about shipping.
