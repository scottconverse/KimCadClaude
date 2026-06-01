import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// KimCad SPA build configuration.
//
// Node/Vite are BUILD-TIME ONLY. `npm run build` compiles this React/TS app to plain
// static files that land in ../src/kimcad/web, which KimCad's local Python server then
// serves (see src/kimcad/webapp.py). Nothing here ships or runs at runtime on the
// target box — the committed build output is what the Python server reads from disk.
//
// Filenames are STABLE (un-hashed) on purpose: the build output is committed to the repo
// so it can be served without a Node toolchain, and stable names mean each rebuild
// overwrites cleanly instead of accumulating orphaned hashed bundles. `emptyOutDir: false`
// keeps the hand-vendored web/vendor/ (legacy three.js, still served at /vendor/) intact.
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: '../src/kimcad/web',
    emptyOutDir: false,
    assetsDir: 'assets',
    rollupOptions: {
      output: {
        entryFileNames: 'assets/kimcad.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
})
