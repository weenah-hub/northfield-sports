/*
  Checkout page
  =============
  Two-column layout: a shipping form on the left, an order summary on the right.

  Flow notes:
  - The cart survives the Google sign-in redirect because it lives in
    localStorage, so a signed-out visitor can sign in and land back here.
  - Quantities are editable right here, which is why "Edit cart" stays on
    this page rather than bouncing the user back to the shop.
*/

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCart } from '../CartContext'
import { useAuth } from '../AuthContext'
import { api, beginGoogleSignIn, isSignInAvailable } from '../api'
import { formatPrice } from '../format'
import OrderSummary from '../components/OrderSummary'

const SHIPPING_FLAT_RATE = 6.95
const FREE_SHIPPING_THRESHOLD = 100
const TAX_RATE = 0.0825

const EMPTY_FORM = {
  shipping_name: '',
  shipping_address: '',
  shipping_city: '',
  shipping_zip: '',
  shipping_country: 'United States',
}

export default function Checkout() {
  const { lines, subtotal, itemCount, hasStockProblem, setQuantity, remove, clear } = useCart()
  const { user, initialising } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState(() => ({
    ...EMPTY_FORM,
    // Pre-fill the recipient from the signed-in account where we can.
    shipping_name: user?.name ?? '',
  }))
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [signInReady, setSignInReady] = useState(null) // null = still checking

  // Find out up front whether Google sign-in is configured, so a misconfigured
  // server shows a clear message instead of dumping the customer on a JSON page.
  useEffect(() => {
    let cancelled = false
    isSignInAvailable().then((ready) => {
      if (!cancelled) setSignInReady(ready)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const shipping = subtotal >= FREE_SHIPPING_THRESHOLD || subtotal === 0 ? 0 : SHIPPING_FLAT_RATE
  const tax = round2(subtotal * TAX_RATE)
  const total = round2(subtotal + shipping + tax)
  const amountToFreeShipping = round2(FREE_SHIPPING_THRESHOLD - subtotal)

  function updateField(field) {
    return (event) => {
      setForm((current) => ({ ...current, [field]: event.target.value }))
      setErrors((current) => ({ ...current, [field]: undefined }))
    }
  }

  function validate() {
    const nextErrors = {}
    const required = {
      shipping_name: 'Enter the recipient name',
      shipping_address: 'Enter the street address',
      shipping_city: 'Enter the city',
      shipping_zip: 'Enter the postcode',
    }
    for (const [field, message] of Object.entries(required)) {
      if (!form[field].trim()) nextErrors[field] = message
    }
    if (form.shipping_zip.trim() && form.shipping_zip.trim().length < 3) {
      nextErrors.shipping_zip = 'That does not look like a valid postcode'
    }
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitError('')

    // Validate before anything else, so a customer is never bounced to Google
    // only to come back to the same empty form.
    if (!validate()) return
    if (hasStockProblem) {
      setSubmitError('Please fix the quantities highlighted below before placing your order.')
      return
    }

    if (!user) {
      // Form is valid — send them through Google, then return straight back here.
      beginGoogleSignIn('/checkout')
      return
    }

    setSubmitting(true)
    try {
      const order = await api.placeOrder({
        items: lines.map((line) => ({
          product_id: line.productId,
          quantity: line.quantity,
        })),
        ...form,
      })

      clear()
      navigate(`/order/${order.id}`, { state: { order } })
    } catch (err) {
      setSubmitError(err.message)
      setSubmitting(false)
    }
  }

  /* ----- Empty cart ----- */
  if (lines.length === 0) {
    return (
      <div className="page">
        <h1 className="page-title">Checkout</h1>
        <div className="empty-state">
          <span className="empty-icon" aria-hidden="true">🛒</span>
          <h2>Your cart is empty</h2>
          <p>Add a few things to the cart and come back to check out.</p>
          <button className="btn btn-primary" onClick={() => navigate('/')}>
            Browse the shop
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <h1 className="page-title">Checkout</h1>

      <div className="checkout-grid">
        {/* ----- Left column: details ----- */}
        <div className="checkout-main">
          <section className="panel">
            <h2 className="panel-title">
              <span className="step-badge">1</span> Contact
            </h2>

            {initialising ? (
              <p className="muted">Checking your session…</p>
            ) : user ? (
              <div className="signed-in-note">
                <span aria-hidden="true">✓</span>
                <div>
                  Signed in as <strong>{user.email}</strong>
                </div>
              </div>
            ) : signInReady === false ? (
              <div className="signin-prompt signin-unavailable">
                <p>
                  <strong>Sign-in is not available on this server.</strong> Google OAuth needs
                  <code> GOOGLE_CLIENT_ID </code> and <code> GOOGLE_CLIENT_SECRET </code> in
                  <code> backend/.env</code>. See the README for setup.
                </p>
              </div>
            ) : (
              <div className="signin-prompt">
                <p>
                  Sign in with Google to place your order. Your cart is saved, so you will come
                  straight back here.
                </p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => beginGoogleSignIn('/checkout')}
                  disabled={signInReady === null}
                >
                  <span aria-hidden="true">G</span> Sign in with Google
                </button>
              </div>
            )}
          </section>

          <section className="panel">
            <h2 className="panel-title">
              <span className="step-badge">2</span> Shipping address
            </h2>

            <form onSubmit={handleSubmit} noValidate>
              <div className="field-grid">
                <Field
                  label="Full name"
                  name="shipping_name"
                  value={form.shipping_name}
                  onChange={updateField('shipping_name')}
                  error={errors.shipping_name}
                  autoComplete="name"
                  className="field-full"
                />
                <Field
                  label="Street address"
                  name="shipping_address"
                  value={form.shipping_address}
                  onChange={updateField('shipping_address')}
                  error={errors.shipping_address}
                  autoComplete="street-address"
                  className="field-full"
                />
                <Field
                  label="City"
                  name="shipping_city"
                  value={form.shipping_city}
                  onChange={updateField('shipping_city')}
                  error={errors.shipping_city}
                  autoComplete="address-level2"
                />
                <Field
                  label="Postcode"
                  name="shipping_zip"
                  value={form.shipping_zip}
                  onChange={updateField('shipping_zip')}
                  error={errors.shipping_zip}
                  autoComplete="postal-code"
                />
                <Field
                  label="Country"
                  name="shipping_country"
                  value={form.shipping_country}
                  onChange={updateField('shipping_country')}
                  error={errors.shipping_country}
                  autoComplete="country-name"
                  className="field-full"
                />
              </div>

              <div className="payment-placeholder">
                <h3>Payment</h3>
                <p>
                  No card is charged on this page. The order is recorded as{' '}
                  <code>pending</code> and a receipt is emailed to you.
                </p>
              </div>

              {submitError && (
                <div className="alert alert-error" role="alert">
                  {submitError}
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary btn-block btn-lg"
                disabled={submitting}
              >
                {submitting ? 'Placing your order…' : `Place order · ${formatPrice(total)}`}
              </button>
            </form>
          </section>
        </div>

        {/* ----- Right column: summary ----- */}
        <aside className="checkout-aside">
          <OrderSummary
            lines={lines}
            itemCount={itemCount}
            subtotal={subtotal}
            shipping={shipping}
            tax={tax}
            total={total}
            amountToFreeShipping={amountToFreeShipping}
            onSetQuantity={setQuantity}
            onRemove={remove}
          />
        </aside>
      </div>
    </div>
  )
}

function Field({ label, error, className = '', ...inputProps }) {
  return (
    <label className={`field ${className}`}>
      <span className="field-label">{label}</span>
      <input
        {...inputProps}
        className={error ? 'has-error' : ''}
        aria-invalid={error ? 'true' : undefined}
      />
      {error && <span className="field-error">{error}</span>}
    </label>
  )
}

function round2(value) {
  return Math.round(value * 100) / 100
}
