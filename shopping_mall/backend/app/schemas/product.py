from __future__ import annotations
import json
from typing import Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class ProductCategory(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    id: int
    name: str


class ProductStore(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    id: int
    name: str
    rating: float = 0.0


class ProductListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    name: str
    price: int
    discount_rate: int = 0
    thumbnail: Optional[str] = None
    rating: float = 0.0
    review_count: int = 0
    sales_count: int = 0
    store_name: Optional[str] = None

    @field_validator("store_name", mode="before")
    @classmethod
    def _store_name(cls, v: Any, info: Any) -> Optional[str]:
        if v is not None:
            return v
        # Populated by CRUD via column_property or manual assignment
        return None


class ProductDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    name: str
    description: Optional[str] = None
    price: int
    discount_rate: int = 0
    category_id: Optional[int] = None
    store_id: Optional[int] = None
    thumbnail: Optional[str] = None
    images: List[str] = []
    options: List[Any] = []
    stock: int = 0
    rating: float = 0.0
    review_count: int = 0
    sales_count: int = 0
    created_at: Optional[datetime] = None
    category: Optional[ProductCategory] = None
    store: Optional[ProductStore] = None

    @field_validator("images", mode="before")
    @classmethod
    def _parse_images(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @field_validator("options", mode="before")
    @classmethod
    def _parse_options(cls, v: Any) -> List[Any]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []


class ProductListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    items: List[ProductListItem]
    total: int
    page: int
    limit: int
    total_pages: int
