from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class OrderItemProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    id: int
    name: str
    thumbnail: Optional[str] = None


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    product_id: int
    quantity: int
    price: int
    selected_option: Optional[str] = None
    product: Optional[OrderItemProduct] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    user_id: int
    total_price: int
    status: str
    shipping_address: Optional[str] = None
    payment_method: Optional[str] = None
    created_at: Optional[datetime] = None
    items: List[OrderItemResponse] = []


class OrderCreate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    shipping_address: Optional[str] = None
    payment_method: Optional[str] = "card"
