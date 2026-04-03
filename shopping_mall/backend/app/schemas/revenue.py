from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class RevenueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    date: str
    order_id: Optional[int] = None
    product_id: Optional[int] = None
    quantity: int
    unit_price: int
    total_amount: int
    category: str
