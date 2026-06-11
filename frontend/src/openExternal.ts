// Stage 11 Slice 11.6 — open a link OUTSIDE the app. In the installed shell the page
// runs inside a WebView2 app window, where a normal link/window.open would navigate the
// APP away from KimCad — the shell exposes window.pywebview.api.open_external (http(s)
// only, opens the system browser). In a normal browser tab (`kimcad web`), window.open
// is exactly right.
type PywebviewBridge = { api?: { open_external?: (url: string) => void } }

export function openExternal(url: string): void {
  const bridge = (window as unknown as { pywebview?: PywebviewBridge }).pywebview
  if (bridge?.api?.open_external) {
    bridge.api.open_external(url)
    return
  }
  window.open(url, '_blank', 'noopener')
}
