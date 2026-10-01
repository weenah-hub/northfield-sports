/*
  Cart context
  ============
  Cart lives in localStorage so it survives a page reload and — importantly —
  the Google sign-in redirect, which navigates away from the app and back.

  Only product ID and quantity are stored. Prices are always read from the
  server so the cart can never show a tampered total.
*/

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from './api'

const CartContext = createContext(null)

const CART_KEY = 'shop_cart'

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
  const [lines, setLines] = useState(readStoredCart)
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    localStorage.setItem(CART_KEY, JSON.stringify(lines))
  }, [lines])

  // Re-fetch the catalogue so prices and stock stay current, then join it to the cart.
  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const data = await api.listProducts()
        if (!cancelled) setProducts(data)
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
  }, [])

  const add = useCallback((productId, quantity = 1) => {
    setLines((current) => {
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
  }, [])

  const setQuantity = useCallback((productId, quantity) => {
    setLines((current) => {
      if (quantity <= 0) return current.filter((line) => line.productId !== productId)
      return current.map((line) =>
        line.productId === productId ? { ...line, quantity } : line
      )
    })
  }, [])

  const remove = useCallback((productId) => {
    setLines((current) => current.filter((line) => line.productId !== productId))
  }, [])

  const clear = useCallback(() => setLines([]), [])

  const detailedLines = useMemo(
    () =>
      lines
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
        .filter(Boolean),
    [lines, products]
  )

  const itemCount = detailedLines.reduce((sum, line) => sum + line.quantity, 0)
  const subtotal = round2(detailedLines.reduce((sum, line) => sum + line.lineTotal, 0))
  const hasStockProblem = detailedLines.some((line) => line.exceedsStock)

  const value = useMemo(
    () => ({
      lines: detailedLines,
      itemCount,
      subtotal,
      hasStockProblem,
      loading,
      error,
      add,
      setQuantity,
      remove,
      clear,
    }),
    [detailedLines, itemCount, subtotal, hasStockProblem, loading, error, add, setQuantity, remove, clear]
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
