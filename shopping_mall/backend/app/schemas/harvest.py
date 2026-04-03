from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class HarvestCreate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    product_id: int
    harvest_date: str
    estimated_quantity: int
    status: str = "planned"


class HarvestUpdate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    harvest_date: Optional[str] = None
    estimated_quantity: Optional[int] = None
    actual_quantity: Optional[int] = None
    status: Optional[str] = None


class HarvestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    product_id: int
    harvest_date: str
    estimated_quantity: int
    actual_quantity: Optional[int] = None
    status: str
