from typing import List
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.crud.order import create_order, get_orders, get_order
from app.schemas.order import OrderResponse, OrderCreate

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _get_user_id(x_user_id: int = Header(default=1, alias="X-User-Id")):
    return x_user_id


@router.post("/", response_model=OrderResponse)
def place_order(
    body: OrderCreate,
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    order = create_order(db, user_id=user_id, shipping_address=body.shipping_address, payment_method=body.payment_method)
    if not order:
        raise HTTPException(status_code=400, detail="Cart is empty")
    return order


@router.get("/", response_model=List[OrderResponse])
def list_orders(user_id: int = Depends(_get_user_id), db: Session = Depends(get_db)):
    return get_orders(db, user_id)


@router.get("/{order_id}", response_model=OrderResponse)
def read_order(order_id: int, db: Session = Depends(get_db)):
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
