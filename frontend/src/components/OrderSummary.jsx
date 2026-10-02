/*
  Order summary
  =============
  Reused on the checkout page. Also handles the "add more" note when the
  customer is close to the free-shipping threshold.
*/

import { Link } from 'react-router-dom'
import { formatPrice } from '../format'
import { slugify } from './ProductCard'

export default function OrderSummary({
  lines,
  itemCount,
  subtotal,
  shipping,
  tax,
  total,
  amountToFreeShipping = 0,
  serverStockProblems = [],
  onSetQuantity,
  onRemove,
}) {
  return (
    <section className="panel summary">
      <h2 className="panel-title">Order summary</h2>

      {amountToFreeShipping > 0 && shipping > 0 && (
        <p className="shipping-nudge">
          Add <strong>{formatPrice(amountToFreeShipping)}</strong> more for free shipping.
        </p>
      )}

      {serverStockProblems.length > 0 && (
        <div className="alert alert-error" role="alert">
          <strong>Some items need attention</strong>
          <ul className="stock-problems">
            {serverStockProblems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}

      <ul className="summary-lines">
        {lines.map((line) => (
          <li key={line.productId} className="summary-line">
            <div className={`summary-thumb cat-${slugify(line.product.category)}`}>
              {line.product.image_url ? (
                <img src={line.product.image_url} alt="" />
              ) : (
                <span aria-hidden="true">
                  {line.product.name
                    .split(/\s+/)
                    .slice(0, 2)
                    .map((w) => w[0])
                    .join('')}
                </span>
              )}
            </div>

            <div className="summary-info">
              <span className="summary-name">{line.product.name}</span>
              <span className="summary-unit">{formatPrice(line.product.price)} each</span>

              {onSetQuantity && (
                <div className="qty qty-sm">
                  <button
                    onClick={() => onSetQuantity(line.productId, line.quantity - 1)}
                    aria-label={`Decrease quantity of ${line.product.name}`}
                  >
                    −
                  </button>
                  <span>{line.quantity}</span>
                  <button
                    onClick={() => onSetQuantity(line.productId, line.quantity + 1)}
                    aria-label={`Increase quantity of ${line.product.name}`}
                  >
                    +
                  </button>
                </div>
              )}

              {line.exceedsStock && (
                <span className="summary-warning">
                  Only {line.product.stock} in stock
                </span>
              )}
            </div>

            <div className="summary-line-right">
              <strong>{formatPrice(line.lineTotal)}</strong>
              {onRemove && (
                <button
                  className="link-btn"
                  onClick={() => onRemove(line.productId)}
                  aria-label={`Remove ${line.product.name} from cart`}
                >
                  Remove
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>

      <dl className="totals">
        <div className="totals-row">
          <dt>Subtotal ({itemCount} {itemCount === 1 ? 'item' : 'items'})</dt>
          <dd>{formatPrice(subtotal)}</dd>
        </div>
        <div className="totals-row">
          <dt>Shipping</dt>
          <dd>{shipping === 0 ? <span className="free">Free</span> : formatPrice(shipping)}</dd>
        </div>
        <div className="totals-row">
          <dt>Estimated tax</dt>
          <dd>{formatPrice(tax)}</dd>
        </div>
        <div className="totals-row totals-grand">
          <dt>Total</dt>
          <dd>{formatPrice(total)}</dd>
        </div>
      </dl>

      {onSetQuantity && (
        <Link className="link-btn edit-cart" to="/">
          ← Add more items
        </Link>
      )}
    </section>
  )
}
