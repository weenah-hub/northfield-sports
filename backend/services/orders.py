"""
Order service
=============
Business rules for turning a checkout request into a real order.

Important: the total is always recalculated here from database prices. The
client sends product IDs and quantities only, so a tampered or stale cart can
never change what the customer is charged.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

import pricing
from models import Order, OrderItem, Product, User
from schemas import OrderCreate


def quote_cart(db: Session, payload: OrderCreate) -> dict:
    """Price a cart the same way `create_order` will, without saving anything.

    Used by `POST /api/orders/quote` so the checkout page can display a total
    that the server itself produced, rather than re-implementing the maths in
    the browser.
    """
    quantities = _collapse_quantities(payload.items)

    subtotal = 0.0
    for product_id, quantity in quantities.items():
        product = db.get(Product, product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} no longer exists.",
            )
        subtotal += product.price * quantity

    return pricing.quote(subtotal)


def _collapse_quantities(items) -> dict[int, int]:
    """Merge duplicate lines for the same product.

    Without this, a cart listing the same product twice would have its stock
    checked once per line and could oversell.
    """
    quantities: dict[int, int] = {}
    for item in items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
    return quantities


def create_order(db: Session, user: User, payload: OrderCreate) -> Order:
    """Validate stock, price the cart server-side, and persist the order."""
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your cart is empty.",
        )

    quantities = _collapse_quantities(payload.items)

    products: dict[int, Product] = {}
    for product_id, quantity in quantities.items():
        product = db.get(Product, product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} no longer exists.",
            )
        if product.stock < quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f'Only {product.stock} left of "{product.name}".'
                    if product.stock > 0
                    else f'"{product.name}" is out of stock.'
                ),
            )
        products[product_id] = product

    # Price the goods, then add shipping and tax using the shared rules.
    # Every money figure below comes from `pricing`; the browser's opinion of
    # the total is never involved.
    subtotal = 0.0
    for product_id, quantity in quantities.items():
        subtotal += products[product_id].price * quantity

    totals = pricing.quote(subtotal)

    order = Order(
        user_id=user.id,
        subtotal=totals["subtotal"],
        shipping=totals["shipping"],
        tax=totals["tax"],
        total=totals["total"],
        status="pending",
        shipping_name=payload.shipping_name.strip(),
        shipping_address=payload.shipping_address.strip(),
        shipping_city=payload.shipping_city.strip(),
        shipping_zip=payload.shipping_zip.strip(),
        shipping_country=payload.shipping_country.strip(),
    )

    for product_id, quantity in quantities.items():
        product = products[product_id]
        # Snapshot the price so later price changes never rewrite history.
        order.items.append(
            OrderItem(
                product_id=product.id,
                quantity=quantity,
                price=product.price,
            )
        )
        product.stock -= quantity

    db.add(order)
    db.commit()

    # Reload the order with its items and products already attached, while the
    # session is definitely still open.
    #
    # The receipt is built in a background task that runs after this request has
    # finished. If it lazy-loaded `items` there it would depend on the database
    # session outliving the request, and email failures are swallowed by
    # design — so a detached instance would mean a customer silently never gets
    # their receipt.
    #
    # This must be an explicit query, not `db.get(id, options=...)`: the order
    # we just created is still in the session's identity map, and `get()` skips
    # the loader options for an object it already has, which would leave
    # `items` unpopulated and reintroduce the very lazy load we are avoiding.
    return (
        db.query(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .filter(Order.id == order.id)
        .one()
    )


def list_orders_for_user(db: Session, user: User) -> list[Order]:
    """Return the user's orders, newest first."""
    return (
        db.query(Order)
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .all()
    )
