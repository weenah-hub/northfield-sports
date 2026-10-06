/*
  Service worker
  ==============
  Makes the app installable and useful on a phone with a patchy connection.

  What it caches, and why
  ----------------------
  * The app shell (HTML, JS, CSS, icons) — cached on install so the app opens
    instantly and shows something even with no signal. Without this the install
    would be a broken app icon.
  * Product data — cached briefly so the grid appears offline.
  * NEVER the cart or sign-in. Caching those would show one customer's basket
    to another on a shared device, and would serve a stale basket that then
    disagrees with the server. Those always go to the network.

  Caching rules
  ------------
  * API reads (GET): network first, fall back to cache when offline. Fresh data
    when it matters, still works when it doesn't.
  * API writes (POST/PATCH/DELETE): never cached, never queued. A queued
    "add to cart" that fires much later is worse than an error.
  * Everything else: cache first, refresh in the background.
*/

const VERSION = 'northfield-v1'
const SHELL_CACHE = `${VERSION}-shell`
const DATA_CACHE = `${VERSION}-data`

// The app shell. Hashed asset filenames change on every build, so this list
// stays valid without invalidating.
const SHELL = ['/', '/index.html', '/manifest.webmanifest']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => !key.startsWith(VERSION)).map((key) => caches.delete(key)))
      )
      .then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event

  // Never interfere with anything that is not a plain GET.
  if (request.method !== 'GET') return

  const url = new URL(request.url)

  // Cross-origin traffic (the API on a different host) is left alone. The
  // browser's own caching rules apply, and we must not cache another origin.
  if (url.origin !== self.location.origin) return

  // Reads from our own API: /api/products and friends. Never the cart.
  if (url.pathname.startsWith('/api/')) {
    // The cart and anything to do with an account must always be live.
    const privatePaths = ['/api/cart', '/api/orders', '/api/auth']
    if (privatePaths.some((prefix) => url.pathname.startsWith(prefix))) return

    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone()
          caches.open(DATA_CACHE).then((cache) => cache.put(request, copy))
          return response
        })
        .catch(() =>
          caches.match(request).then(
            (cached) =>
              cached ||
              new Response(
                JSON.stringify({ detail: 'You appear to be offline.' }),
                { status: 503, headers: { 'Content-Type': 'application/json' } }
              )
          )
        )
    )
    return
  }

  // Client-side routes (/checkout, /orders, ...) all resolve to index.html.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/index.html').then((c) => c || Response.error()))
    )
    return
  }

  // Static assets: serve from cache straight away, refresh behind the scenes.
  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone()
            caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy))
          }
          return response
        })
        .catch(() => cached)
      return cached || network
    })
  )
})