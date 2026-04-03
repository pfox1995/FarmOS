from sqlalchemy.orm import Session, joinedload
from app.models.order import Order, OrderItem
from app.models.cart import CartItem
from app.models.product import Product


def create_order(db: Session, user_id: int, shipping_address: str | None = None, payment_method: str = "card"):
    cart_items = db.query(CartItem).filter(CartItem.user_id == user_id).all()
    if not cart_items:
        return None
    total_price = 0
    order_items = []
    for ci in cart_items:
        product = db.query(Product).filter(Product.id == ci.product_id).first()
        if product:
            discounted = product.price * (100 - product.discount_rate) // 100
            item_total = discounted * ci.quantity
            total_price += item_total
            order_items.append(
                OrderItem(
                    product_id=ci.product_id,
                    quantity=ci.quantity,
                    price=item_total,
                    selected_option=ci.selected_option,
                )
            )
    order = Order(
        user_id=user_id,
        total_price=total_price,
        status="pending",
        shipping_address=shipping_address,
        payment_method=payment_method,
    )
    db.add(order)
    db.flush()
    for oi in order_items:
        oi.order_id = order.id
        db.add(oi)
    db.query(CartItem).filter(CartItem.user_id == user_id).delete()
    db.commit()
    db.refresh(order)
    return order


def get_orders(db: Session, user_id: int):
    return (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(OrderItem.product))
        .filter(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .all()
    )


def get_order(db: Session, order_id: int):
    return (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(OrderItem.product))
        .filter(Order.id == order_id)
        .first()
    )
