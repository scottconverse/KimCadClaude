import React from 'react'
import ReactDOM from 'react-dom/client'
// The Workshop fonts are self-hosted via @fontsource-variable and declared latin-only in
// styles.css (KimCad's UI is English; the other subsets would be committed dead weight).
import App from './App'
import { initTheme } from './useTheme'
import './styles.css'

// KC-18 (#23): apply the persisted (or system) theme before the first render, so a
// dark-preference user never sees a light flash on load.
initTheme()

const root = document.getElementById('root')
if (!root) throw new Error('KimCad: #root element missing from index.html')

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
