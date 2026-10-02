/*
  API client
  ==========
  One place that knows the backend URL and attaches the auth token.
*/

// Where the API lives.
//
// Three cases, in order of preference:
//
// 1. VITE_API_URL is set  -> use it. This is what a split deployment needs,
//    where the static site (e.g. Netlify) and the API (e.g. Render) are on
//    different domains. Without this the browser would look for /api/products
//    on the static host and get a 404.
// 2. Built for production, no VITE_API_URL -> the API is on the same origin,
//    which is how it works when FastAPI serves the built frontend itself.
// 3. Local development -> FastAPI on port 8000.
const API = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? '' : 'http://localhost:8000')
).replace(/\/+$/, '')

const TOKEN_KEY = 'shop_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/** Full URL for a backend path, e.g. apiUrl('/api/products') */
export function apiUrl(path) {
  return `${API}${path}`
}

/**
 * Fetch wrapper. Throws an Error with a readable `message` on failure so
 * callers can surface the server's message directly to the user.
 */
export async function request(path, { method = 'GET', body, auth = false } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let response
  try {
    response = await fetch(apiUrl(path), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new Error('Cannot reach the server. Is the backend running?')
  }

  if (response.status === 204) return null

  let data = null
  try {
    data = await response.json()
  } catch {
    // Non-JSON error body (e.g. an HTML 500 page).
    if (!response.ok) throw new Error(`Request failed (${response.status})`)
    return null
  }

  if (!response.ok) {
    const detail =
      typeof data?.detail === 'string' ? data.detail : 'Something went wrong.'
    throw new Error(detail)
  }

  return data
}

/* ---------- Typed helpers ---------- */

export const api = {
  listProducts: (params = {}) => {
    const query = new URLSearchParams()
    if (params.category && params.category !== 'All') query.set('category', params.category)
    if (params.search) query.set('search', params.search)
    const qs = query.toString()
    return request(`/api/products${qs ? `?${qs}` : ''}`)
  },

  listCategories: () => request('/api/products/categories'),

  me: () => request('/api/auth/me', { auth: true }),

  /**
   * Ask the server to price the cart.
   *
   * The checkout page must never work out money itself — the shipping and tax
   * rules live on the server, so duplicating them here is how a shop ends up
   * quoting one total and storing another. Send product IDs and quantities and
   * render whatever comes back.
   */
  quoteCart: (items) => request('/api/orders/quote', { method: 'POST', body: { items } }),

  placeOrder: (payload) => request('/api/orders', { method: 'POST', body: payload, auth: true }),

  getOrder: (id) => request(`/api/orders/${id}`, { auth: true }),
}

/**
 * Check whether the server has Google sign-in configured.
 *
 * Without this the sign-in button would navigate the browser to the API and
 * land on a raw JSON error page, which looks broken to a customer.
 */
export async function isSignInAvailable() {
  try {
    const response = await fetch(apiUrl('/api/auth/google'), { redirect: 'manual' })
    // A redirect means Google is wired up and the flow can start.
    return response.type === 'opaqueredirect' || response.status === 307
  } catch {
    return false
  }
}

/** Kick off the Google redirect flow, returning to `path` afterwards. */
export function beginGoogleSignIn(path = '/') {
  window.location.href = apiUrl(`/api/auth/google?redirect=${encodeURIComponent(path)}`)
}
