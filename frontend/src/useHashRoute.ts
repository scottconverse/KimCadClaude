import { useEffect, useState } from 'react'

// Stage 8.5 — a tiny hash-based router. Routes: '' (landing/new), 'designs' (the My Designs
// library), 'design/<id>' (a saved design). Hash routing keeps the stdlib server simple — it only
// ever serves '/', and a refresh on '#/designs' or '#/design/<id>' still loads the app, then the
// app reads the hash. No dependency, no server-side SPA fallback.

export type Route =
  | { name: 'landing' }
  | { name: 'designs' }
  | { name: 'design'; id: string }

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#\/?/, '')
  if (h === 'designs') return { name: 'designs' }
  if (h.startsWith('design/')) {
    const id = decodeURIComponent(h.slice('design/'.length))
    if (id) return { name: 'design', id }
  }
  return { name: 'landing' }
}

/** The current route + a `navigate(to)` that sets the hash (e.g. `navigate('designs')`,
 * `navigate('design/<id>')`, `navigate('')`). `replace` swaps the entry instead of pushing one. */
export function useHashRoute(): {
  route: Route
  navigate: (to: string, opts?: { replace?: boolean }) => void
} {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash))
  useEffect(() => {
    const onHash = () => setRoute(parseHash(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const navigate = (to: string, opts?: { replace?: boolean }) => {
    const url = `#/${to}`
    if (opts?.replace) {
      window.history.replaceState(null, '', url)
      setRoute(parseHash(url)) // replaceState doesn't fire hashchange — update directly
    } else {
      window.location.hash = `/${to}`
    }
  }
  return { route, navigate }
}
