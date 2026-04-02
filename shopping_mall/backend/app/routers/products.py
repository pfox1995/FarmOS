from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.crud.product import get_products, get_product, search_products
from app.schemas.product import ProductListResponse, ProductListItem, ProductDetail

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/", response_model=ProductListResponse)
def list_products(
    page: int = 1,
    limit: int = 20,
    category_id: Optional[int] = None,
    sort: str = "latest",
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    db: Session = Depends(get_db),
):
    result = get_products(db, page=page, limit=limit, category_id=category_id, sort=sort, min_price=min_price, max_price=max_price)
    return result


@router.get("/search", response_model=ProductListResponse)
def search(q: str = "", page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    result = search_products(db, q=q, page=page, limit=limit)
    return result


@router.get("/{product_id}", response_model=ProductDetail)
def read_product(product_id: int, db: Session = Depends(get_db)):
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
