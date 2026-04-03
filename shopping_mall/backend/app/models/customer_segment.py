from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CustomerSegment(Base):
    __tablename__ = "shop_customer_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_users.id"), unique=True, nullable=False)
    segment: Mapped[str] = mapped_column(String(20), nullable=False)
    recency_days: Mapped[int] = mapped_column(Integer, default=0)
    frequency: Mapped[int] = mapped_column(Integer, default=0)
    monetary: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(default=func.now())

    user = relationship("User")
