from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class CartItemProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    id: int
    name: str
    price: int
    discount_rate: int = 0
    thumbnail: Optional[str] = None


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    product_id: int
    quantity: int
    selected_option: Optional[str] = None
    product: Optional[CartItemProduct] = None


class CartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    items: List[CartItemResponse]
    total_price: int


class CartItemCreate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    product_id: int
    quantity: int = 1
    selected_option: Optional[str] = None


class CartItemUpdate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    quantity: int
