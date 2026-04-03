from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class ShipmentCreate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    order_id: int
    carrier: str
    tracking_number: str


class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    order_id: int
    carrier: str
    tracking_number: str
    status: str
    last_checked_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    tracking_history: Optional[str] = None
    created_at: Optional[datetime] = None
