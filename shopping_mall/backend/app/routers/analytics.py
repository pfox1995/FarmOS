"""Analytics and customer segmentation router."""
from datetime import date, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.customer_segment import CustomerSegment
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.revenue import RevenueEntry
from app.models.expense import ExpenseEntry
from app.models.user import User
from app.schemas.segment import CustomerSegmentResponse, SegmentSummary
from app.services.rfm_analyzer import RFMAnalyzer

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/segments", response_model=List[SegmentSummary])
def get_segment_summary(db: Session = Depends(get_db)):
    """Get summary of customer segments."""
    results = RFMAnalyzer.get_segment_summary(db)
    return results


@router.get("/segments/{segment}", response_model=List[CustomerSegmentResponse])
def get_customers_in_segment(segment: str, db: Session = Depends(get_db)):
    """Get all customers in a specific segment."""
    valid_segments = {"vip", "loyal", "repeat", "new", "at_risk", "dormant"}
    if segment not in valid_segments:
        raise HTTPException(status_code=400, detail=f"Invalid segment. Must be one of: {valid_segments}")
    customers = (
        db.query(CustomerSegment)
        .filter(CustomerSegment.segment == segment)
        .all()
    )
    return customers


@router.post("/segments/refresh")
def refresh_segments(db: Session = Depends(get_db)):
    """Recalculate all customer segments using RFM analysis."""
    count = RFMAnalyzer.analyze_all(db)
    return {"updated_count": count}


@router.get("/popular-items")
def get_popular_items(
    top_n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get top N popular items by sales count."""
    items = (
        db.query(
            Product.id,
            Product.name,
            Product.price,
            Product.sales_count,
            Product.rating,
            Product.thumbnail,
        )
        .order_by(Product.sales_count.desc())
        .limit(top_n)
        .all()
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "salesCount": item.sales_count,
            "rating": item.rating,
            "thumbnail": item.thumbnail,
        }
        for item in items
    ]


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """Combined dashboard stats for backoffice main page."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    today_str = today.isoformat()
    yesterday_str = yesterday.isoformat()

    # --- Today's revenue ---
    today_revenue = (
        db.query(func.coalesce(func.sum(RevenueEntry.total_amount), 0))
        .filter(RevenueEntry.category == "sales", RevenueEntry.date == today_str)
        .scalar()
    ) or 0

    yesterday_revenue = (
        db.query(func.coalesce(func.sum(RevenueEntry.total_amount), 0))
        .filter(RevenueEntry.category == "sales", RevenueEntry.date == yesterday_str)
        .scalar()
    ) or 0

    # --- Today's orders ---
    today_orders = (
        db.query(func.count(Order.id))
        .filter(cast(Order.created_at, Date) == today)
        .scalar()
    ) or 0

    yesterday_orders = (
        db.query(func.count(Order.id))
        .filter(cast(Order.created_at, Date) == yesterday)
        .scalar()
    ) or 0

    # --- New customers (registered today) ---
    new_customers = (
        db.query(func.count(User.id))
        .filter(cast(User.created_at, Date) == today)
        .scalar()
    ) or 0

    yesterday_customers = (
        db.query(func.count(User.id))
        .filter(cast(User.created_at, Date) == yesterday)
        .scalar()
    ) or 0

    # --- Change rates (%) ---
    def calc_change(current: float, previous: float) -> float:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / previous) * 100

    revenue_change = calc_change(today_revenue, yesterday_revenue)
    orders_change = calc_change(today_orders, yesterday_orders)
    customers_change = calc_change(new_customers, yesterday_customers)

    # --- Weekly revenue (last 7 days) ---
    week_ago = today - timedelta(days=6)
    weekly_rows = (
        db.query(
            RevenueEntry.date,
            func.coalesce(func.sum(RevenueEntry.total_amount), 0),
        )
        .filter(
            RevenueEntry.category == "sales",
            RevenueEntry.date >= week_ago.isoformat(),
            RevenueEntry.date <= today_str,
        )
        .group_by(RevenueEntry.date)
        .order_by(RevenueEntry.date)
        .all()
    )
    revenue_by_date = {row[0]: int(row[1]) for row in weekly_rows}
    weekly_revenue = []
    for i in range(7):
        d = (week_ago + timedelta(days=i)).isoformat()
        weekly_revenue.append({"date": d, "revenue": revenue_by_date.get(d, 0)})

    # --- Customer segments ---
    segment_rows = RFMAnalyzer.get_segment_summary(db)
    segments = [
        {"name": s["segment"], "count": s["count"]}
        for s in segment_rows
    ]

    return {
        "today_revenue": today_revenue,
        "today_orders": today_orders,
        "new_customers": new_customers,
        "revenue_change": round(revenue_change, 1),
        "orders_change": round(orders_change, 1),
        "customers_change": round(customers_change, 1),
        "weekly_revenue": weekly_revenue,
        "segments": segments,
    }
