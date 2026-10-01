/*
  Product card
  ============
  Single product tile with quantity control and add-to-cart.
*/

import { useState } from 'react'
import { useCart } from '../CartContext'
import { formatPrice } from '../format'

export default function ProductCard({ product }) {
  const { add } = useCart()
  const [quantity, setQuantity] = useState(1)
  const [justAdded, setJustAdded] = useState(false)

  const soldOut = product.stock === 0
  const inCart = product.stock > 0

  function handleAdd() {
    add(product.id, quantity)
    setJustAdded(true)
    setTimeout(() => setJustAdded(false), 1400)
  }

  return (
    <article className="product-card">
      <div className={`product-media cat-${slugify(product.category)}`}>
        {product.image_url ? (
          <img src={product.image_url} alt={product.name} loading="lazy" />
        ) : (
          <span className="product-media-fallback" aria-hidden="true">
            {initials(product.name)}
          </span>
        )}
        <span className={`stock-pill ${soldOut ? 'out' : product.stock <= 5 ? 'low' : ''}`}>
          {soldOut ? 'Sold out' : product.stock <= 5 ? `Only ${product.stock} left` : 'In stock'}
        </span>
      </div>

      <div className="product-body">
        <span className="product-category">{product.category}</span>
        <h3 className="product-name">{product.name}</h3>
        <p className="product-description">{product.description}</p>
        <strong className="product-price">{formatPrice(product.price)}</strong>
      </div>

      <div className="product-actions">
        <div className="qty" role="group" aria-label={`Quantity for ${product.name}`}>
          <button
            onClick={() => setQuantity((q) => Math.max(1, q - 1))}
            disabled={!inCart}
            aria-label="Decrease quantity"
          >
            −
          </button>
          <span>{quantity}</span>
          <button
            onClick={() => setQuantity((q) => Math.min(product.stock, q + 1))}
            disabled={!inCart}
            aria-label="Increase quantity"
          >
            +
          </button>
        </div>

        <button className="btn btn-primary add-btn" onClick={handleAdd} disabled={soldOut}>
          {justAdded ? 'Added ✓' : soldOut ? 'Sold out' : 'Add to cart'}
        </button>
      </div>
    </article>
  )
}

export function slugify(value = '') {
  return String(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

function initials(name = '') {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join('')
}
