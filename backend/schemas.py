"""
Pydantic schemas
===============
Define the shape of data sent to and from the API.
These validate incoming requests and format outgoing responses.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# ---------- Product schemas ----------
class ProductBase(BaseModel):
    name: str
    description: str = ""
    price: float = Field(gt=0)
    image_url: str = ""
    category: str = "General"
    stock: int = Field(default=0, ge=0)


class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Order schemas ----------

class CartItem(BaseModel):
    """One line in a cart: which product, and how many. No prices.

    Prices are deliberately absent so a modified browser cannot influence what
    the customer is charged. The server looks up every price itself.
    """

    product_id: int
    quantity: int = Field(gt=0, le=100)


class QuoteRequest(BaseModel):
    """A cart to be priced, for display on the checkout page."""

    items: list[CartItem]


class QuoteResponse(BaseModel):
    """The server's own price breakdown for a cart."""

    subtotal: float
    shipping: float
    tax: float
    total: float
    # Sent so the page can nudge the customer toward free shipping without
    # hardcoding a threshold that the server may change.
    free_shipping_threshold: float
    # Set when a line cannot be bought as it stands, so the page can warn the
    # customer before they try to pay.
    out_of_stock: list[str] = []
    max_quantities: dict[int, int] = {}


class OrderItemCreate(CartItem):
    pass


# ---------- Cart schemas ----------

class CartItemCreate(BaseModel):
    """Add a product to the saved cart. No price is accepted."""

    product_id: int
    quantity: int = Field(default=1, gt=0, le=99)


class CartQuantityUpdate(BaseModel):
    """Set an exact quantity. Zero removes the line."""

    quantity: int = Field(ge=0, le=99)


class MergeRequest(BaseModel):
    """A guest cart to fold into the account's cart after signing in."""

    items: list[CartItemCreate] = []


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    price: float
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    items: list[OrderItemCreate]
    shipping_name: str = Field(min_length=1, max_length=255)
    shipping_address: str = Field(min_length=1)
    shipping_city: str = Field(min_length=1, max_length=100)
    shipping_zip: str = Field(min_length=1, max_length=20)
    shipping_country: str = Field(default="United States", min_length=1, max_length=100)


class OrderResponse(BaseModel):
    id: int
    subtotal: float
    shipping: float
    tax: float
    total: float
    status: str
    shipping_name: str
    shipping_address: str
    shipping_city: str
    shipping_zip: str
    shipping_country: str
    created_at: datetime
    items: list[OrderItemResponse]

    class Config:
        from_attributes = True


# ---------- User/Auth schemas ----------
class UserResponse(BaseModel):
    id: int
    email: str
    name: str

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    token: str
    user: UserResponse
