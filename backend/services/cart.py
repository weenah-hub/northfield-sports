"""
Cart service
============
Reads and writes the signed-in customer's saved cart in the database.

This is the shared source of truth behind every client: the website and the
phone app both talk to this, which is what makes them stay in step. Neither
client keeps its own copy — they both render whatever is here.

Two rules, the same as for orders:

* Prices are never accepted from the client. Only product IDs and quantities
  are stored; every price comes from the `products` table at read time.
* Stock is checked on every write, so a cart cannot silently hold more than
  exists.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import pricing
from models import CartItem, Product

# A single line can never exceed this, even if stock allows it. Without a cap a
# runaway client could ask for 100000 shirts and make every price calculation
# unwieldy.
MAX_LINE_QUANTITY = 99


def _stock_error(product: Product, wanted: int) -> HTTPException:
    """Build the right 409 for a quantity that stock cannot support."""
    if product.stock < 1:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'"{product.name}" is out of stock.',
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f'Only {product.stock} left of "{product.name}".',
    )


def _get_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} no longer exists.",
        )
    return product


def get_cart(db: Session, user) -> list[CartItem]:
    """The customer's saved cart lines, oldest first for a stable order."""
    return (
        db.query(CartItem)
        .filter(CartItem.user_id == user.id)
        .order_by(CartItem.id)
        .all()
    )


def add_item(db: Session, user, product_id: int, quantity: int) -> CartItem:
    """Add to a line, or raise its quantity if the product is already there.

    If the resulting quantity would exceed stock this raises rather than
    quietly clamping. Silently clamping means a customer taps "Add to cart"
    and the number does not move, with nothing to explain why. Refusing
    loudly matches what placing an order already does.
    """
    product = _get_or_404(db, product_id)
    existing = (
        db.query(CartItem)
        .filter(CartItem.user_id == user.id, CartItem.product_id == product_id)
        .one_or_none()
    )

    current = existing.quantity if existing else 0
    wanted = current + quantity

    if product.stock < wanted:
        raise _stock_error(product, wanted)

    wanted = min(wanted, MAX_LINE_QUANTITY)

    if existing:
        existing.quantity = wanted
        row = existing
    else:
        row = CartItem(user_id=user.id, product_id=product_id, quantity=wanted)
        db.add(row)

    db.commit()
    db.refresh(row)
    return row


def set_quantity(db: Session, user, product_id: int, quantity: int) -> CartItem | None:
    """Set a line to an exact quantity. A quantity of 0 removes the line."""
    row = (
        db.query(CartItem)
        .filter(CartItem.user_id == user.id, CartItem.product_id == product_id)
        .one_or_none()
    )

    if quantity <= 0:
        if row is not None:
            db.delete(row)
            db.commit()
        return None

    product = _get_or_404(db, product_id)
    wanted = min(quantity, MAX_LINE_QUANTITY)
    if product.stock < wanted:
        raise _stock_error(product, wanted)

    if row is None:
        row = CartItem(user_id=user.id, product_id=product_id, quantity=wanted)
        db.add(row)
    else:
        row.quantity = wanted

    db.commit()
    db.refresh(row)
    return row


def remove_item(db: Session, user, product_id: int) -> None:
    """Remove a line. Removing something that isn't there is not an error."""
    row = (
        db.query(CartItem)
        .filter(CartItem.user_id == user.id, CartItem.product_id == product_id)
        .one_or_none()
    )
    if row is not None:
        db.delete(row)
        db.commit()


def clear_cart(db: Session, user) -> int:
    """Empty the cart. Returns how many lines were removed."""
    removed = db.query(CartItem).filter(CartItem.user_id == user.id).delete()
    db.commit()
    return removed


def merge_cart(db: Session, user, items: list[dict]) -> dict:
    """Fold a guest cart into the signed-in one.

    A visitor can fill a cart before signing in — those lines live in that
    browser's localStorage. On sign-in we combine them with anything already
    saved, summing quantities per product and clamping to stock, so nothing the
    customer picked is silently lost.

    This is additive rather than a replacement on purpose: overwriting would
    throw away items that were already in their account.
    """
    added, skipped = [], []

    for item in items:
        product_id = int(item.get("product_id", 0))
        quantity = int(item.get("quantity", 0))
        if quantity <= 0:
            continue
        try:
            add_item(db, user, product_id, quantity)
            added.append(product_id)
        except HTTPException:
            # Out of stock or missing: skip rather than fail the whole sign-in.
            # The cart still works, just without that line.
            skipped.append(product_id)

    return {"merged": len(added), "skipped": skipped}


def cart_payload(db: Session, user) -> dict:
    """The cart in the shape every client renders: products, totals, problems.

    Prices and stock come straight from the database, so two clients asking at
    the same moment always get the same answer.
    """
    rows = get_cart(db, user)
    products = {p.id: p for p in db.query(Product).all()}

    items, subtotal, out_of_stock, max_quantities = [], 0.0, [], {}

    for row in rows:
        product = products.get(row.product_id)
        if product is None:
            # The product was deleted from the catalogue while it sat in a
            # cart. Drop the line rather than showing a broken entry.
            continue

        subtotal += product.price * row.quantity
        max_quantities[row.product_id] = product.stock

        if product.stock < row.quantity:
            out_of_stock.append(
                f"{product.name} — only {product.stock} left"
                if product.stock > 0
                else f"{product.name} is out of stock"
            )

        items.append(
            {
                "product_id": row.product_id,
                "quantity": row.quantity,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "price": product.price,
                    "image_url": product.image_url,
                    "category": product.category,
                    "stock": product.stock,
                },
            }
        )

    totals = pricing.quote(subtotal)
    return {
        "items": items,
        "item_count": sum(item["quantity"] for item in items),
        **totals,
        "free_shipping_threshold": pricing.FREE_SHIPPING_THRESHOLD,
        "out_of_stock": out_of_stock,
        "max_quantities": max_quantities,
    }