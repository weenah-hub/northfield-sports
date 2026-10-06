/*
  Entry point — this is the FIRST file that runs
  It loads React and renders the App component into the #root div
*/

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './App.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

/*
  Service worker registration — this is what makes the site installable as an
  app on a phone, and lets it open with no signal.

  Skipped in development: the worker caches aggressively, which makes code
  changes appear not to work because you are looking at an old cached bundle.
  Only production gets it, so `npm run dev` behaves normally.
*/
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error) => {
      // A failed registration costs offline support but nothing else, and it
      // should never take the page down with it.
      console.warn('Service worker registration failed:', error)
    })
  })
}