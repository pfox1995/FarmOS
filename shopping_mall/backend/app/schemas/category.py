from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class CategoryBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    name: str
    icon: Optional[str] = None
    sort_order: int = 0


class CategoryChild(CategoryBase):
    pass


class CategoryTree(CategoryBase):
    children: List[CategoryChild] = []
