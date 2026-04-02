from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    rating: float = 0.0
    product_count: int = 0
