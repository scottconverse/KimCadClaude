# KimCad frontend (React + TypeScript + Vite)

This is the source for KimCad's browser UI. It compiles to plain static files that
KimCad's local Python server serves. **Node and Vite are build-time only** — they never
run on the target box and never ship. The compiled output is committed to the repo so the
app runs with no Node toolchain.

## How it fits together

```
frontend/                 ← this app (React + TS source)  ── npm run build ──▶  src/kimcad/web/
  src/                                                                           index.html   (SPA shell, served at /)
  index.html  (Vite entry)                                                       assets/      (bundled JS/CSS/fonts, served at /assets/)
  vite.config.ts                                                                 vendor/      (legacy three.js, served at /vendor/)
```

`src/kimcad/webapp.py` (a dependency-free stdlib `http.server`) serves the build output:
the shell at `/`, the bundles at `/assets/<file>` (same path-traversal guard as `/vendor/`).
The JSON API the SPA talks to (`/api/design`, `/api/slice/<id>`, `/api/options`,
`/api/connector-status/<name>`, `/api/mesh/<id>`, `/api/gcode/<id>`, `/api/send/<id>`) is
unchanged from the pre-SPA UI — the build only changes the front end, not the contract.

## Develop

```
npm ci          # install pinned deps (uses package-lock.json)
npm run dev      # Vite dev server with HMR (developer convenience only — never the product)
```

The dev server proxies nothing by default; run `kimcad web` separately for the real API, or
point the SPA at it. For most work, `npm run build` + `kimcad web` is the faithful path.

## Build (this is what ships)

```
npm ci
npm run build    # tsc --noEmit (typecheck) + vite build → writes ../src/kimcad/web/{index.html,assets/}
```

- Output filenames are **stable** (un-hashed: `assets/kimcad.js`, `assets/index.css`) so each
  rebuild overwrites cleanly and the committed output stays tidy.
- `emptyOutDir` is **false** so the hand-vendored `web/vendor/` (legacy three.js) survives.
- **Commit the rebuilt `src/kimcad/web/` along with the source change** — the server serves the
  committed files, so a source edit without a rebuilt, committed bundle is a no-op at runtime.

## Verify

```
npm test          # vitest — unit tests for the pure logic (api client, status mappers)
```

`tests/test_frontend.py` (the built shell mounts `#root`, references existing `/assets/`
bundles, carries the Workshop tokens + fonts, and consumes every documented backend field) and
`tests/test_webapp.py` (the server serves `/` and `/assets/` and rejects traversal) gate the
build output from the Python side, so a missing or stale build trips the suite. `npm test`
(vitest) covers the TypeScript logic and is run by `scripts/ci.sh` when the toolchain is present.
