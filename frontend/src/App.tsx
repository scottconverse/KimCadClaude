// KimCad SPA — application shell.
//
// Stage 4, Slice 1: the build→serve seam and a minimal Workshop-themed shell (topbar +
// empty viewport). The three-column layout, conversation/parameter/report panels, the
// real Three.js viewport, and the wired design→gate→slice→download flow arrive in the
// following Stage 4 slices.
export default function App() {
  return (
    <div className="kc-shell">
      <header className="kc-topbar">
        <div className="kc-brand">
          <span className="kc-logo" aria-hidden="true" />
          <span className="kc-wordmark">
            Kim<span className="kc-wordmark-accent">Cad</span>
          </span>
        </div>
      </header>
      <main className="kc-main">
        <section className="kc-viewport" aria-label="3D preview">
          <p className="kc-viewport-empty">Describe a part to see it here.</p>
        </section>
      </main>
    </div>
  )
}
