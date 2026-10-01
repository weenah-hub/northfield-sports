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
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


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
