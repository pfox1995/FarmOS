from typing import List
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models.wishlist import Wishlist
from app.models.product import Product
from app.schemas.product import ProductListItem

router = APIRouter(prefix="/api/wishlists", tags=["wishlists"])


def _get_user_id(x_user_id: int = Header(default=1, alias="X-User-Id")):
    return x_user_id


@router.get("/", response_model=List[ProductListItem])
def get_wishlist(user_id: int = Depends(_get_user_id), db: Session = Depends(get_db)):
    wishlists = (
        db.query(Wishlist)
        .options(joinedload(Wishlist.product))
        .filter(Wishlist.user_id == user_id)
        .order_by(Wishlist.created_at.desc())
        .all()
    )
    return [w.product for w in wishlists if w.product]


@router.post("/{product_id}")
def toggle_wishlist(
    product_id: int,
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Wishlist)
        .filter(Wishlist.user_id == user_id, Wishlist.product_id == product_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        return {"wishlisted": False}
    else:
        w = Wishlist(user_id=user_id, product_id=product_id)
        db.add(w)
        db.commit()
        return {"wishlisted": True}
