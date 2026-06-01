// Right column — parameters + printability.
//
// Slice 3 is a static scaffold. The real parameter list (read-only in Stage 4; live sliders
// are Stage 5) and the printability report (gate status, target-vs-actual dimensions, findings)
// are wired from /api/design's response in Slice 4.
export default function RightPanel() {
  return (
    <aside className="kc-col-right">
      <section className="kc-card">
        <h2 className="kc-card-title">Parameters</h2>
        <p className="kc-muted-note">
          The part&rsquo;s adjustable parameters will appear here once it&rsquo;s designed.
        </p>
      </section>
      <section className="kc-card">
        <h2 className="kc-card-title">Printability</h2>
        <p className="kc-muted-note">
          The printability check — dimensions, wall thickness, build-volume fit — appears here
          after a part is designed.
        </p>
      </section>
    </aside>
  )
}
