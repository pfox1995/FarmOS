from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.store import Store
from app.models.product import Product
from app.schemas.store import StoreResponse
from app.schemas.product import ProductListItem

router = APIRouter(prefix="/api/stores", tags=["stores"])


@router.get("/{store_id}", response_model=StoreResponse)
def read_store(store_id: int, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/{store_id}/products", response_model=list[ProductListItem])
def store_products(store_id: int, db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.store_id == store_id).order_by(Product.created_at.desc()).all()
    return products
