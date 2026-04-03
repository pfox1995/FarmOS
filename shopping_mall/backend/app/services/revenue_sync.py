"""Sync completed orders into revenue_entries table."""
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem
from app.models.revenue import RevenueEntry


def sync_orders_to_revenue(db: Session) -> int:
    """Find orders not yet in revenue_entries and create entries. Returns count of new entries."""
    # Get order IDs already synced
    synced_order_ids = {
        row[0]
        for row in db.query(RevenueEntry.order_id)
        .filter(RevenueEntry.order_id.isnot(None))
        .all()
    }

    # Get completed orders not yet synced
    orders = (
        db.query(Order)
        .filter(
            Order.status.in_(["paid", "shipping", "delivered"]),
            Order.id.notin_(synced_order_ids) if synced_order_ids else True,
        )
        .all()
    )

    count = 0
    for order in orders:
        if order.id in synced_order_ids:
            continue

        items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        for item in items:
            entry = RevenueEntry(
                date=order.created_at.strftime("%Y-%m-%d") if order.created_at else "unknown",
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.price // item.quantity if item.quantity else item.price,
                total_amount=item.price,
                category="sales",
            )
            db.add(entry)
            count += 1

    if count > 0:
        db.commit()
    return count
