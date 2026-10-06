/*
  Cart context
  ============
  One cart, shared by every device the customer is signed in on.

  Two modes
  ---------
  * Signed out — the cart lives in this browser's localStorage. Nobody is
    identified, so there is nothing to attach it to. A visitor can fill a
    basket before signing in.
  * Signed in — the cart lives in the database and this component simply
    renders it. That is what makes a change on a laptop show up on a phone:
    both are reading the same rows, not keeping private copies.

  On sign-in the guest cart is merged into the account's cart (POST
  /api/cart/merge), so nothing the customer picked beforehand is lost.

  Sync
  ----
  When signed in, the cart is re-read every few seconds. That is what picks up
  a change made on another device. Polling rather than WebSockets because this
  API is hosted on a service that sleeps when idle, where a persistent socket
  would be dropped anyway.

  Polling pauses while the tab is hidden and resumes (and refreshes at once)
  when it comes back, so a phone in someone's pocket costs nothing.
*/

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { api } from './api'
import { useAuth } from './AuthContext'

const CartContext = createContext(null)

const CART_KEY = 'shop_cart'

// How often to re-read the server cart so changes from other devices appear.
// Three seconds is quick enough to read as instant and light enough that a
// phone on mobile data will not notice.
const SYNC_INTERVAL_MS = 3000

function readStoredCart() {
  try {
    const raw = localStorage.getItem(CART_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed)
      ? parsed
          .map((line) => ({
            productId: Number(line.productId),
            quantity: Math.max(1, Math.floor(Number(line.quantity) || 1)),
          }))
          .filter((line) => Number.isFinite(line.productId))
      : []
  } catch {
    return []
  }
}

export function CartProvider({ children }) {
  const { user, initialising } = useAuth()

  // Guest cart, only used while signed out.
  const [guestLines, setGuestLines] = useState(readStoredCart)

  // Server cart payload while signed in.
  const [serverCart, setServerCart] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Products are needed only to price the guest cart; the server sends the
  // product details along with the signed-in cart.
  const [products, setProducts] = useState([])

  // Guards the one-time guest-to-account merge so it cannot fire twice.
  const mergedFor = useRef(null)
  const signedIn = Boolean(user)

  // ---------- guest cart persistence ----------
  useEffect(() => {
    if (!signedIn) localStorage.setItem(CART_KEY, JSON.stringify(guestLines))
  }, [guestLines, signedIn])

  // ---------- catalogue (for pricing the guest cart) ----------
  useEffect(() => {
    let cancelled = false
    api
      .listProducts()
      .then((data) => {
        if (!cancelled) setProducts(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  // ---------- read the server cart ----------
  const refresh = useCallback(async () => {
    if (!signedIn) return
    try {
      const data = await api.getCart()
      setServerCart(data)
      setError('')
    } catch (err) {
      // A failed refresh is usually a dropped connection or the API waking
      // up. Keep showing the last known cart rather than blanking it.
      setError(err.message)
    }
  }, [signedIn])

  // Load once on sign-in, then merge anything picked up as a guest.
  useEffect(() => {
    if (!signedIn || initialising) return

    let cancelled = false

    async function load() {
      setLoading(true)
      try {
        const data = await api.getCart()
        if (cancelled) return
        setServerCart(data)

        // Merge the guest basket exactly once per account.
        if (mergedFor.current !== user.id) {
          mergedFor.current = user.id
          const guest = readStoredCart()
          if (guest.length > 0) {
            const merged = await api.mergeCart(
              guest.map((line) => ({ product_id: line.productId, quantity: line.quantity }))
            )
            if (cancelled) return
            setServerCart(merged)
          }
          localStorage.removeItem(CART_KEY)
        }
        setError('')
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [signedIn, initialising, user])

  // Signing out means the account's cart is no longer ours to show, and the
  // next guest starts clean.
  useEffect(() => {
    if (signedIn) return
    setServerCart(null)
    setGuestLines([])
    mergedFor.current = null
  }, [signedIn])

  // ---------- polling ----------
  useEffect(() => {
    if (!signedIn || initialising) return

    let timer = null

    function stopPolling() {
      if (timer) {
        clearInterval(timer)
        timer = null
      }
    }

    function startPolling() {
      stopPolling()
      timer = setInterval(refresh, SYNC_INTERVAL_MS)
    }

    function handleVisibility() {
      if (document.hidden) {
        stopPolling()
      } else {
        refresh()
        startPolling()
      }
    }

    startPolling()
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      stopPolling()
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [signedIn, initialising, refresh])

  // ---------- mutations ----------
  // Each one writes to the server (signed in) or localStorage (guest), then
  // updates from the server's response so the client never disagrees with it.

  const add = useCallback(
    async (productId, quantity = 1) => {
      if (signedIn) {
        try {
          setServerCart(
            await api.addToCart({ product_id: productId, quantity })
          )
          setError('')
          return true
        } catch (err) {
          setError(err.message)
          await refresh()
          return false
        }
      }
      setGuestLines((current) => {
        const existing = current.find((line) => line.productId === productId)
        if (existing) {
          return current.map((line) =>
            line.productId === productId
              ? { ...line, quantity: line.quantity + quantity }
              : line
          )
        }
        return [...current, { productId, quantity }]
      })
      return true
    },
    [signedIn, refresh]
  )

  const setQuantity = useCallback(
    async (productId, quantity) => {
      if (signedIn) {
        try {
          setServerCart(
            await api.setCartQuantity(productId, { quantity })
          )
          setError('')
        } catch (err) {
          setError(err.message)
          await refresh()
        }
        return
      }
      setGuestLines((current) => {
        if (quantity <= 0) return current.filter((line) => line.productId !== productId)
        return current.map((line) =>
          line.productId === productId ? { ...line, quantity } : line
        )
      })
    },
    [signedIn, refresh]
  )

  const remove = useCallback(
    async (productId) => {
      if (signedIn) {
        try {
          setServerCart(await api.removeCartItem(productId))
          setError('')
        } catch (err) {
          setError(err.message)
          await refresh()
        }
        return
      }
      setGuestLines((current) => current.filter((line) => line.productId !== productId))
    },
    [signedIn, refresh]
  )

  const clear = useCallback(async () => {
    if (signedIn) {
      try {
        setServerCart(await api.clearCart())
        setError('')
      } catch (err) {
        setError(err.message)
        await refresh()
      }
      return
    }
    setGuestLines([])
  }, [signedIn, refresh])

  // ---------- render-ready view ----------
  // Both modes produce the same shape, so Header, ProductCard and Checkout do
  // not care which one is running.
  const lines = useMemo(() => {
    if (signedIn) {
      return (serverCart?.items ?? []).map((item) => ({
        productId: item.product_id,
        quantity: item.quantity,
        product: item.product,
        lineTotal: round2(item.product.price * item.quantity),
        exceedsStock: item.quantity > item.product.stock,
      }))
    }

    return guestLines
      .map((line) => {
        const product = products.find((p) => p.id === line.productId)
        if (!product) return null
        return {
          ...line,
          product,
          lineTotal: round2(product.price * line.quantity),
          exceedsStock: line.quantity > product.stock,
        }
      })
      .filter(Boolean)
  }, [signedIn, serverCart, guestLines, products])

  const itemCount = lines.reduce((sum, line) => sum + line.quantity, 0)
  const subtotal = round2(lines.reduce((sum, line) => sum + line.lineTotal, 0))
  const hasStockProblem = lines.some((line) => line.exceedsStock)

  // True while another device's change has not arrived yet. Deliberately does
  // not block interaction: the whole point of syncing is that the cart keeps
  // working while it updates.
  const syncing = signedIn && loading && !serverCart

  const value = useMemo(
    () => ({
      lines,
      itemCount,
      subtotal,
      hasStockProblem,
      loading,
      syncing,
      error,
      add,
      setQuantity,
      remove,
      clear,
      refresh,
      // Lets Checkout price the signed-in cart from the same server response
      // instead of making a second round trip.
      serverTotals: signedIn ? serverCart : null,
    }),
    [lines, itemCount, subtotal, hasStockProblem, loading, syncing, error, add, setQuantity, remove, clear, refresh, signedIn, serverCart]
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart() {
  const context = useContext(CartContext)
  if (!context) throw new Error('useCart must be used inside a CartProvider')
  return context
}

function round2(value) {
  return Math.round(value * 100) / 100
}