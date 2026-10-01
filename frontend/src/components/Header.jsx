/*
  Site header
  ===========
  Brand, nav links, cart summary, and sign-in state.
*/

import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useCart } from '../CartContext'
import { useAuth } from '../AuthContext'
import { beginGoogleSignIn } from '../api'
import { formatPrice } from '../format'

export default function Header() {
  const { itemCount, subtotal } = useCart()
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link to="/" className="brand">
          <span className="brand-mark">NS</span>
          <span className="brand-text">
            <strong>Northfield</strong>
            <small>Sports Co.</small>
          </span>
        </Link>

        <nav className="main-nav">
          <NavLink to="/" end>
            Shop
          </NavLink>
          <NavLink to="/orders">Orders</NavLink>
        </nav>

        <div className="header-actions">
          <button
            type="button"
            className="cart-summary"
            onClick={() => navigate('/checkout')}
            aria-label={`Cart, ${itemCount} items, ${formatPrice(subtotal)}`}
          >
            <span aria-hidden="true">🛒</span>
            <span className="cart-count">{itemCount}</span>
            <span className="cart-total">{formatPrice(subtotal)}</span>
          </button>

          {user ? (
            <div className="user-menu">
              <span className="user-name" title={user.email}>
                Hi, {user.name.split(' ')[0]}
              </span>
              <button type="button" className="btn btn-ghost" onClick={signOut}>
                Sign out
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => beginGoogleSignIn('/checkout')}
            >
              Sign in
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
