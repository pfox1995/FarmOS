import math
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from app.models.product import Product
from app.models.store import Store


def get_products(
    db: Session,
    page: int = 1,
    limit: int = 20,
    category_id: Optional[int] = None,
    sort: str = "latest",
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
):
    query = db.query(Product).options(joinedload(Product.store))
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    total = query.count()
    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort == "popular":
        query = query.order_by(Product.sales_count.desc())
    elif sort == "rating":
        query = query.order_by(Product.rating.desc())
    else:
        query = query.order_by(Product.created_at.desc())
    offset = (page - 1) * limit
    items = query.offset(offset).limit(limit).all()
    # Attach store_name for list serialization
    for item in items:
        item.store_name = item.store.name if item.store else None
    total_pages = math.ceil(total / limit) if limit > 0 else 0
    return {"items": items, "total": total, "page": page, "limit": limit, "total_pages": total_pages}


def get_product(db: Session, product_id: int):
    return (
        db.query(Product)
        .options(joinedload(Product.category), joinedload(Product.store))
        .filter(Product.id == product_id)
        .first()
    )


def search_products(db: Session, q: str, page: int = 1, limit: int = 20):
    query = db.query(Product).filter(Product.name.contains(q))
    total = query.count()
    offset = (page - 1) * limit
    items = query.order_by(Product.created_at.desc()).offset(offset).limit(limit).all()
    total_pages = math.ceil(total / limit) if limit > 0 else 0
    return {"items": items, "total": total, "page": page, "limit": limit, "total_pages": total_pages}
