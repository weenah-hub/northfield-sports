/*
  Order confirmation
  ==================
  Reached right after a successful checkout. The order object is passed
  through router state so this renders instantly, with a refetch as a
  fallback (e.g. on a hard refresh).
*/

import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api } from '../api'
import { formatDate, formatPrice } from '../format'

export default function OrderConfirmation() {
  const { orderId } = useParams()
  const { state } = useLocation()
  const [order, setOrder] = useState(state?.order ?? null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (order) return
    let cancelled = false

    api
      .getOrder(orderId)
      .then((data) => {
        if (!cancelled) setOrder(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })

    return () => {
      cancelled = true
    }
  }, [order, orderId])

  if (error) {
    return (
      <div className="page">
        <div className="empty-state">
          <h2>We could not find that order</h2>
          <p>{error}</p>
          <Link className="btn btn-primary" to="/">
            Back to the shop
          </Link>
        </div>
      </div>
    )
  }

  if (!order) {
    return (
      <div className="page">
        <div className="empty-state">
          <p>Loading your order…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page narrow">
      <div className="confirmation">
        <span className="confirmation-icon" aria-hidden="true">✓</span>
        <h1>Thanks, {order.shipping_name.split(' ')[0]}!</h1>
        <p className="confirmation-lead">
          Your order <strong>#{order.id}</strong> is confirmed. A receipt is on its way to your
          inbox.
        </p>

        <div className="panel">
          <div className="order-meta">
            <div>
              <span className="meta-label">Placed</span>
              <span className="meta-value">{formatDate(order.created_at)}</span>
            </div>
            <div>
              <span className="meta-label">Status</span>
              <span className="meta-value status">{order.status}</span>
            </div>
            <div>
              <span className="meta-label">Total</span>
              <span className="meta-value">{formatPrice(order.total)}</span>
            </div>
          </div>

          <ul className="summary-lines">
            {order.items.map((item) => (
              <li key={item.id} className="summary-line">
                <div className="summary-info">
                  <span className="summary-name">{item.product?.name ?? `Product #${item.product_id}`}</span>
                  <span className="summary-unit">
                    {item.quantity} × {formatPrice(item.price)}
                  </span>
                </div>
                <div className="summary-line-right">
                  <strong>{formatPrice(item.price * item.quantity)}</strong>
                </div>
              </li>
            ))}
          </ul>

          {/* Orders placed before the breakdown was stored have subtotal 0.
              Showing a $0.00 subtotal next to a real total would be a lie, so
              fall back to just the total for those. */}
          {order.subtotal > 0 ? (
            <dl className="totals">
              <div className="totals-row">
                <dt>Subtotal</dt>
                <dd>{formatPrice(order.subtotal)}</dd>
              </div>
              <div className="totals-row">
                <dt>Shipping</dt>
                <dd>
                  {order.shipping === 0 ? (
                    <span className="free">Free</span>
                  ) : (
                    formatPrice(order.shipping)
                  )}
                </dd>
              </div>
              <div className="totals-row">
                <dt>Tax</dt>
                <dd>{formatPrice(order.tax)}</dd>
              </div>
            </dl>
          ) : null}

          <dl className="totals">
            <div className="totals-row totals-grand">
              <dt>Total</dt>
              <dd>{formatPrice(order.total)}</dd>
            </div>
          </dl>

          <div className="ship-to">
            <span className="meta-label">Shipping to</span>
            <p>
              {order.shipping_name}
              <br />
              {order.shipping_address}
              <br />
              {order.shipping_city}, {order.shipping_zip}
              <br />
              {order.shipping_country}
            </p>
          </div>
        </div>

        <div className="confirmation-actions">
          <Link className="btn btn-primary" to="/">
            Continue shopping
          </Link>
          <Link className="btn btn-outline" to="/orders">
            View all orders
          </Link>
        </div>
      </div>
    </div>
  )
}
