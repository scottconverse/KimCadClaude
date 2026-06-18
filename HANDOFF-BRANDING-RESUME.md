# Resume prompt — KimCad branding overhaul (paused for Codex reinstall)

**Branch:** `kim-branding-overhaul` (NOT pushed) · **`main` untouched** · **Date paused:** 2026-06-18

## Where we are
Scott reviewed the side-by-side package at `docs/redesign/SIDE-BY-SIDE.html` and **approved everything**:
- Landing page rewrite — promoted to `docs/index.html`
- Palette evolution to Zen Design World **gold/black** (across the whole app)
- **"Kim Everywhere"** — Kim's face is the brand mark
- All 7 held in-app branding items (avatar upgrade, favicon, wizard, native window, empty-state, a11y, installer)

Paused for a Codex update reinstall. Resume by executing the full work list below.

## The full work list (do these in order)

### Step 1 — Asset upgrade (lowest risk)
- Replace `frontend/src/assets/kim-avatar.png` with a 256px crop of the 1254px master at `docs/assets/kim-avatar.png`. Use Pillow `LANCZOS` resample. Verify file size ~35-50KB.

### Step 2 — Repalette the app to gold/black
Rewrite the CSS variables in `frontend/src/styles.css` (around lines 44-58 light, 109-120 dark) to Zen Design World tokens:

```
/* light */
--kc-bg:        #fafaf7;
--kc-surface:   #ffffff;
--kc-surface-2: #f4f1ea;
--kc-ink:       #0c0a06;
--kc-hair:      #e8e4d8;
--kc-hair-strong:#d6d0bf;
--kc-accent:        #d4af37;   /* Kim's gold */
--kc-accent-strong: #b8901f;
--kc-accent-deep:   #8f6e15;
--kc-accent-soft:   #f3e6a5;
--kc-accent-bg:     #faf2d4;

/* dark */
--kc-bg:        #0c0a06;
--kc-surface:   #161310;
--kc-surface-2: #1f1c17;
--kc-ink:       #f5efe5;
--kc-hair:      #2a2620;
--kc-hair-strong:#3a3530;
--kc-accent:        #e3c24f;
--kc-accent-strong: #efd06b;
--kc-accent-deep:   #c9a634;
--kc-accent-soft:   #4a3d18;
--kc-accent-bg:     #2a2210;
```

Update the comment block (line 3) — replace "Workshop terracotta" with "Zen Design World gold/black". Verify with `npm --prefix frontend run build` then the demo at port 8701.

### Step 3 — Favicon (flip the deliberate 204)
- Copy `docs/assets/kim.ico` → `frontend/public/favicon.ico` and `docs/assets/kim-96.png` → `frontend/public/kim-favicon.png`.
- In `frontend/index.html` `<head>` add:
  ```html
  <link rel="icon" type="image/png" sizes="96x96" href="/kim-favicon.png">
  <link rel="apple-touch-icon" href="/kim-favicon.png">
  ```
- In `src/kimcad/webapp.py:938-942`: replace the 204 branch — serve `WEB_DIR / "favicon.ico"` (200, `image/x-icon`) if it exists, else fall back to 204.
- `npm --prefix frontend run build`, verify tab + window chrome show Kim.

### Step 4 — Welcome wizard (Kim's face)
- `frontend/src/components/FirstRunWizard.tsx`:
  - Add `import kimAvatar from '../assets/kim-avatar.png'` at the top.
  - In `.kc-wiz-brand` rail (line ~249), insert before the wordmark:
    `<img src={kimAvatar} alt="Kim" className="kc-wiz-avatar" />` (~56px round with gold ring)
  - In the Welcome step (step 0, line ~274), add above the `<h1>`:
    `<img src={kimAvatar} alt="Kim" className="kc-wiz-welcome-avatar" />` (~120px round with gold ring)
- Add to `frontend/src/styles.css`:
  ```css
  .kc-wiz-avatar { width:56px; height:56px; border-radius:50%;
    box-shadow: 0 0 0 2px var(--kc-accent), 0 2px 8px rgba(0,0,0,.12);
    display:block; margin: 0 0 12px; }
  .kc-wiz-welcome-avatar { width:120px; height:120px; border-radius:50%;
    box-shadow: 0 0 0 3px var(--kc-accent), 0 8px 24px rgba(0,0,0,.16);
    display:block; margin: 0 auto 24px; }
  ```

### Step 5 — Empty-state Landing (Kim mark near hero)
- `frontend/src/components/Landing.tsx`: add `<img src={kimAvatar} alt="Kim" className="kc-landing-avatar" />` above `<h1 className="kc-hero-title">` (line ~117).
- Add to styles.css:
  ```css
  .kc-landing-avatar { width:96px; height:96px; border-radius:50%;
    box-shadow: 0 0 0 2.5px var(--kc-accent), 0 6px 18px rgba(0,0,0,.14);
    display:block; margin: 0 auto 18px; }
  ```

### Step 6 — A11y (replace background-image brand spans)
- `frontend/src/styles.css` lines 224 and 2486 — find `.kc-ava` and `.kc-logo` classes (or whatever the brand background-image hooks are named) and identify their JSX usage. Replace `<span class="kc-ava" aria-hidden="true">` with `<img src={kimAvatar} alt="Kim" className="kc-ava" />`. Remove the `background-image` declaration, keep size + radius styling.

### Step 7 — Native window icon
- Copy `docs/assets/kim.ico` → `src/kimcad/web/kim.ico` so it ships with the package.
- In `src/kimcad/shell.py:124` (the `webview.create_window(...)` call), pass the icon:
  ```python
  webview.create_window(..., icon=str(Path(__file__).parent / "web" / "kim.ico"))
  ```
  Verify the parameter name in current pywebview API; it may need to be passed via `webview.start(icon=...)` instead.

### Step 8 — Installer .exe + desktop + Start-menu icon (HEAVY — rebuild required)
- Copy `docs/assets/kim.ico` → `installer/kim.ico`.
- In `installer/kimcad.iss` `[Setup]` add:
  ```
  SetupIconFile=kim.ico
  UninstallDisplayIcon={app}\src\kimcad\web\kim.ico
  ```
- Both `[Icons]` entries: add `IconFilename: "{app}\src\kimcad\web\kim.ico"`
- **Rebuild installer:** `iscc installer/kimcad.iss` then run on a clean Windows test profile to confirm .exe icon + desktop shortcut + Start-menu tile all show Kim.

### Step 9 — Verify + gate + push
1. `npm --prefix frontend run build` — SPA build clean
2. Run the e2e suite: `pytest tests/e2e/` — should be green
3. Run `/gauntletgate all` if Scott authorizes, or at minimum `/audit-lite` on the diff
4. Push only after Scott has eyes on the final result and explicitly says push.

## Where the prepared assets live
- `docs/assets/kim-avatar.png` — 1254×1254px master (Kim's face, the source of truth)
- `docs/assets/kim-256.png`, `kim-180.png`, `kim-96.png`, `kim-48.png`, `kim-32.png` — derived sizes
- `docs/assets/kim.ico` — multi-resolution Windows icon (16/32/48/64/128/256)
- `docs/assets/og-card.png` — 1200×630 social share card

## Review artifacts (already shipped on this branch — don't redo)
- [docs/index.html](docs/index.html) — the new landing page (already promoted from `docs/redesign/index.html`)
- [docs/redesign/SIDE-BY-SIDE.html](docs/redesign/SIDE-BY-SIDE.html) — the approved review package (6 sections, 37 captures)
- [docs/redesign/APP-BRANDING-PLAN.md](docs/redesign/APP-BRANDING-PLAN.md) — original spec, supersede with this handoff
- [docs/redesign/DESIGN-DIRECTION.md](docs/redesign/DESIGN-DIRECTION.md) — Kim's brand book findings
- Capture scripts (kept for re-runs): `docs/redesign/capture_compare.py`, `capture_palette.py`, `capture_inapp_branding.py`

## Standing rules in force
- Never push without Scott's explicit OK on the specific change.
- Branch stays `kim-branding-overhaul` until everything above is green AND Scott reviews the rebuilt app.
- Kim's face is the brand mark — every surface above gets it.
- All-zero audit before merge (`/audit-lite` minimum, `/gauntletgate all` ideally).
- KimCad is a gift for Kim — Kim-worthy quality bar, not "ship the minimum."
