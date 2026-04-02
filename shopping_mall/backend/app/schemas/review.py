from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class ReviewUser(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    id: int
    name: str


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    product_id: int
    user_id: int
    rating: float
    content: Optional[str] = None
    images: Optional[str] = None
    created_at: Optional[datetime] = None
    user: Optional[ReviewUser] = None
