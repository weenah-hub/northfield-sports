"""
Order service
=============
Business rules for turning a checkout request into a real order.

Important: the total is always recalculated here from database prices. The
client sends product IDs and quantities only, so a tampered or stale cart can
never change what the customer is charged.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import Order, OrderItem, Product, User
from schemas import OrderCreate


def create_order(db: Session, user: User, payload: OrderCreate) -> Order:
    """Validate stock, price the cart server-side, and persist the order."""
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your cart is empty.",
        )

    # Collapse duplicate lines for the same product so stock is checked per product.
    quantities: dict[int, int] = {}
    for item in payload.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity

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

    order = Order(
        user_id=user.id,
        total=0.0,
        status="pending",
        shipping_name=payload.shipping_name.strip(),
        shipping_address=payload.shipping_address.strip(),
        shipping_city=payload.shipping_city.strip(),
        shipping_zip=payload.shipping_zip.strip(),
    )

    total = 0.0
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
        total += product.price * quantity
        product.stock -= quantity

    order.total = round(total, 2)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def list_orders_for_user(db: Session, user: User) -> list[Order]:
    """Return the user's orders, newest first."""
    return (
        db.query(Order)
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .all()
    )
