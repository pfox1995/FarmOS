"""AI-powered weekly report generation service."""
import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.revenue import RevenueEntry
from app.models.expense import ExpenseEntry
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.weekly_report import WeeklyReport

logger = logging.getLogger(__name__)


class ReportService:
    """Generate weekly business reports with optional AI insights."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def generate_weekly(self, week_start: str, week_end: str, db: Session) -> WeeklyReport:
        """Generate a weekly report for the given date range."""
        # Aggregate revenue
        total_revenue = (
            db.query(func.coalesce(func.sum(RevenueEntry.total_amount), 0))
            .filter(
                RevenueEntry.date >= week_start,
                RevenueEntry.date <= week_end,
                RevenueEntry.category == "sales",
            )
            .scalar()
        ) or 0

        # Aggregate expenses
        total_expense = (
            db.query(func.coalesce(func.sum(ExpenseEntry.amount), 0))
            .filter(
                ExpenseEntry.date >= week_start,
                ExpenseEntry.date <= week_end,
            )
            .scalar()
        ) or 0

        net_profit = total_revenue - total_expense

        # Get top items
        top_items_query = (
            db.query(
                Product.name,
                func.sum(OrderItem.quantity).label("total_qty"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .filter(
                Order.created_at >= datetime.strptime(week_start, "%Y-%m-%d"),
                Order.created_at <= datetime.strptime(week_end, "%Y-%m-%d"),
                Order.status != "cancelled",
            )
            .group_by(Product.id)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(5)
            .all()
        )
        top_items = [{"name": name, "quantity": qty} for name, qty in top_items_query]

        # Order count
        order_count = (
            db.query(func.count(Order.id))
            .filter(
                Order.created_at >= datetime.strptime(week_start, "%Y-%m-%d"),
                Order.created_at <= datetime.strptime(week_end, "%Y-%m-%d"),
                Order.status != "cancelled",
            )
            .scalar()
        ) or 0

        # Generate report content
        report_content = await self._generate_content(
            week_start=week_start,
            week_end=week_end,
            total_revenue=total_revenue,
            total_expense=total_expense,
            net_profit=net_profit,
            order_count=order_count,
            top_items=top_items,
        )

        # Save report
        report = WeeklyReport(
            week_start=week_start,
            week_end=week_end,
            total_revenue=total_revenue,
            total_expense=total_expense,
            net_profit=net_profit,
            report_content=report_content,
            generated_at=datetime.utcnow(),
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    async def _generate_content(self, **data) -> str:
        """Generate report content using LLM or fallback."""
        if self.llm:
            try:
                return await self.llm.generate_report(data)
            except Exception as e:
                logger.warning(f"LLM report generation failed: {e}")

        # Fallback: structured text report
        top_items_str = ", ".join(
            f"{item['name']}({item['quantity']}개)" for item in data.get("top_items", [])
        )
        return (
            f"[주간 리포트 {data['week_start']} ~ {data['week_end']}]\n"
            f"총 매출: {data['total_revenue']:,}원 | 총 비용: {data['total_expense']:,}원 | "
            f"순이익: {data['net_profit']:,}원\n"
            f"주문 건수: {data.get('order_count', 0)}건\n"
            f"인기 상품: {top_items_str or '데이터 없음'}\n"
            f"* AI 분석 서비스 미연결로 자동 인사이트가 생성되지 않았습니다."
        )
