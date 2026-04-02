from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models.cart import CartItem
from app.models.product import Product
from app.schemas.cart import CartResponse, CartItemResponse, CartItemCreate, CartItemUpdate

router = APIRouter(prefix="/api/cart", tags=["cart"])


def _get_user_id(x_user_id: int = Header(default=1, alias="X-User-Id")):
    return x_user_id


@router.get("/", response_model=CartResponse)
def get_cart(user_id: int = Depends(_get_user_id), db: Session = Depends(get_db)):
    items = (
        db.query(CartItem)
        .options(joinedload(CartItem.product))
        .filter(CartItem.user_id == user_id)
        .all()
    )
    total_price = 0
    for item in items:
        if item.product:
            discounted = item.product.price * (100 - item.product.discount_rate) // 100
            total_price += discounted * item.quantity
    return {"items": items, "total_price": total_price}


@router.post("/", response_model=CartItemResponse)
def add_to_cart(
    body: CartItemCreate,
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == body.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (
        db.query(CartItem)
        .filter(CartItem.user_id == user_id, CartItem.product_id == body.product_id)
        .first()
    )
    if existing:
        existing.quantity += body.quantity
        db.commit()
        db.refresh(existing)
        item = db.query(CartItem).options(joinedload(CartItem.product)).filter(CartItem.id == existing.id).first()
        return item

    cart_item = CartItem(
        user_id=user_id,
        product_id=body.product_id,
        quantity=body.quantity,
        selected_option=body.selected_option,
    )
    db.add(cart_item)
    db.commit()
    db.refresh(cart_item)
    item = db.query(CartItem).options(joinedload(CartItem.product)).filter(CartItem.id == cart_item.id).first()
    return item


@router.put("/{item_id}", response_model=CartItemResponse)
def update_cart_item(item_id: int, body: CartItemUpdate, db: Session = Depends(get_db)):
    item = db.query(CartItem).filter(CartItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    item.quantity = body.quantity
    db.commit()
    db.refresh(item)
    result = db.query(CartItem).options(joinedload(CartItem.product)).filter(CartItem.id == item.id).first()
    return result


@router.delete("/{item_id}")
def remove_cart_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(CartItem).filter(CartItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()
    return {"message": "Removed"}
