import React from 'react'
import ReactDOM from 'react-dom/client'
// The Workshop fonts are self-hosted via @fontsource-variable and declared latin-only in
// styles.css (KimCad's UI is English; the other subsets would be committed dead weight).
import App from './App'
import './styles.css'

const root = document.getElementById('root')
if (!root) throw new Error('KimCad: #root element missing from index.html')

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
