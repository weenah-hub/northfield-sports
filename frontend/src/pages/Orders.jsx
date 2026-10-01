/*
  Order history
  =============
  Every past order for the signed-in customer.
*/

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { request, beginGoogleSignIn } from '../api'
import { formatDate, formatPrice } from '../format'
import { useAuth } from '../AuthContext'

export default function Orders() {
  const { user, initialising } = useAuth()
  const navigate = useNavigate()
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (initialising) return
    if (!user) {
      setLoading(false)
      return
    }

    let cancelled = false
    request('/api/orders', { auth: true })
      .then((data) => {
        if (!cancelled) setOrders(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [user, initialising])

  if (!initialising && !user) {
    return (
      <div className="page narrow">
        <h1 className="page-title">Your orders</h1>
        <div className="empty-state">
          <h2>Sign in to see your orders</h2>
          <p>Your order history is tied to your account.</p>
          <button
            className="btn btn-primary"
            onClick={() => beginGoogleSignIn('/orders')}
          >
            Sign in with Google
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="page narrow">
      <h1 className="page-title">Your orders</h1>

      {loading && <p className="muted">Loading your orders…</p>}
      {error && <div className="alert alert-error">{error}</div>}

      {!loading && orders.length === 0 && !error && (
        <div className="empty-state">
          <h2>No orders yet</h2>
          <p>When you place an order it will show up here.</p>
          <button className="btn btn-primary" onClick={() => navigate('/')}>
            Browse the shop
          </button>
        </div>
      )}

      <div className="order-list">
        {orders.map((order) => (
          <Link key={order.id} to={`/order/${order.id}`} className="order-row">
            <div>
              <span className="order-id">Order #{order.id}</span>
              <span className="order-date">{formatDate(order.created_at)}</span>
            </div>
            <div className="order-row-right">
              <span className="status status-sm">{order.status}</span>
              <strong>{formatPrice(order.total)}</strong>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
