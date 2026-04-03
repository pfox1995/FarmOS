"""RFM (Recency, Frequency, Monetary) customer segmentation analyzer."""
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.customer_segment import CustomerSegment
from app.models.user import User


class RFMAnalyzer:
    """Analyze customers using RFM methodology and assign segments."""

    SEGMENT_RULES = [
        # (segment_name, condition_func)
        ("vip", lambda r, f, m: r < 30 and f >= 5 and m >= 500000),
        ("loyal", lambda r, f, m: r < 60 and f >= 3),
        ("repeat", lambda r, f, m: f >= 2),
        ("new", lambda r, f, m: f == 1 and r < 30),
        ("at_risk", lambda r, f, m: r > 60 and f >= 2),
        ("dormant", lambda r, f, m: r > 90),
    ]

    @classmethod
    def _classify_segment(cls, recency: int, frequency: int, monetary: int) -> str:
        for name, condition in cls.SEGMENT_RULES:
            if condition(recency, frequency, monetary):
                return name
        return "new"

    @classmethod
    def analyze_all(cls, db: Session) -> int:
        """Recalculate RFM segments for all users. Returns count of updated users."""
        now = datetime.utcnow()
        users = db.query(User).all()
        updated = 0

        for user in users:
            # Calculate RFM values
            orders = (
                db.query(Order)
                .filter(Order.user_id == user.id, Order.status != "cancelled")
                .all()
            )

            if not orders:
                recency = 999
                frequency = 0
                monetary = 0
            else:
                last_order_date = max(o.created_at for o in orders)
                recency = (now - last_order_date).days
                frequency = len(orders)
                monetary = sum(o.total_price for o in orders)

            segment = cls._classify_segment(recency, frequency, monetary)

            # Upsert
            existing = (
                db.query(CustomerSegment)
                .filter(CustomerSegment.user_id == user.id)
                .first()
            )
            if existing:
                existing.segment = segment
                existing.recency_days = recency
                existing.frequency = frequency
                existing.monetary = monetary
                existing.last_updated = now
            else:
                db.add(
                    CustomerSegment(
                        user_id=user.id,
                        segment=segment,
                        recency_days=recency,
                        frequency=frequency,
                        monetary=monetary,
                        last_updated=now,
                    )
                )
            updated += 1

        db.commit()
        return updated

    @classmethod
    def get_segment_summary(cls, db: Session) -> list[dict]:
        """Return count of customers per segment."""
        results = (
            db.query(CustomerSegment.segment, func.count(CustomerSegment.id))
            .group_by(CustomerSegment.segment)
            .all()
        )
        return [{"segment": seg, "count": cnt} for seg, cnt in results]
