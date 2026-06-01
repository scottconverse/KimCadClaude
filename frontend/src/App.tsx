import Topbar from './components/Topbar'
import Landing from './components/Landing'

// KimCad SPA — application shell.
//
// Stage 4, Slice 2: the Workshop design system (tokens + self-hosted fonts), the topbar
// chrome, and the landing (empty) screen. The three-column workspace layout and the real
// Three.js viewport arrive in Slice 3; the design→gate→slice→download flow is wired in
// Slices 4–5, at which point the landing's input and the topbar's "New design" become live.
export default function App() {
  return (
    <div className="kc-shell">
      <Topbar />
      <Landing />
    </div>
  )
}
