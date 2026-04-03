"""Simple demand forecasting using moving average."""
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem


def forecast_demand(db: Session, product_id: int, weeks: int = 4) -> dict:
    """Calculate moving average of weekly sales for a product over the last N weeks."""
    now = datetime.utcnow()
    weekly_sales = []

    for i in range(weeks):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(weeks=1)

        total = (
            db.query(func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .filter(
                OrderItem.product_id == product_id,
                Order.created_at >= week_start,
                Order.created_at < week_end,
                Order.status != "cancelled",
            )
            .scalar()
        )
        weekly_sales.append({"week": f"W-{i}", "start": week_start.strftime("%Y-%m-%d"), "end": week_end.strftime("%Y-%m-%d"), "quantity": total or 0})

    total_qty = sum(w["quantity"] for w in weekly_sales)
    avg = total_qty / weeks if weeks > 0 else 0

    return {
        "product_id": product_id,
        "weeks_analyzed": weeks,
        "weekly_sales": weekly_sales,
        "moving_average": round(avg, 2),
        "forecast_next_week": round(avg, 0),
    }
