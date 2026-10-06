"""
Database models
==============
These classes define the tables in your Neon PostgreSQL database.
SQLAlchemy translates them into real database tables.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class User(Base):
    """A shop customer who signs in with Google."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    google_id = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Link to orders this user has placed
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")


class Product(Base):
    """A sports kit product in the shop."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    price = Column(Float, nullable=False)
    image_url = Column(String(500), default="")
    category = Column(String(100), default="General")
    stock = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Link to order items
    order_items = relationship("OrderItem", back_populates="product")


class Order(Base):
    """A customer's order."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # The price breakdown, stored separately from `total`.
    # `subtotal` is goods only; shipping and tax are added on top. Keeping each
    # part on the order means the receipt, the order history and the customer's
    # own confirmation screen can all show the same maths, and a later change to
    # the shipping or tax rules cannot retroactively rewrite old orders.
    subtotal = Column(Float, nullable=False, default=0.0)
    shipping = Column(Float, nullable=False, default=0.0)
    tax = Column(Float, nullable=False, default=0.0)
    total = Column(Float, nullable=False)

    status = Column(String(50), default="pending")  # pending, paid, shipped, delivered
    shipping_name = Column(String(255), default="")
    shipping_address = Column(Text, default="")
    shipping_city = Column(String(100), default="")
    shipping_zip = Column(String(20), default="")
    shipping_country = Column(String(100), default="United States")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """A single line item within an order."""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)  # Price at time of purchase

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class CartItem(Base):
    """One product in a signed-in customer's saved cart.

    Why this table exists
    --------------------
    A cart used to live only in the browser's localStorage. That works for one
    device but cannot sync: localStorage is private to one browser on one
    machine, so a phone and a laptop have completely separate carts with no way
    to tell each other. Storing the cart here — keyed to the user — is what
    makes "add on my laptop, see it on my phone" possible.

    Only product IDs and quantities are stored. Prices are always read from
    `products` at read time, so a stale cart can never dictate a price, exactly
    as with orders.
    """

    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    # When the line was last touched. Lets clients apply only newer changes
    # instead of blindly overwriting a cart another device just updated.
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # One row per product per customer: adding the same product twice must
    # raise the quantity, never create a duplicate line.
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),)

    user = relationship("User")
    product = relationship("Product")
