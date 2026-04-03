from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class HarvestSchedule(Base):
    __tablename__ = "shop_harvest_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_products.id"), nullable=False)
    harvest_date: Mapped[str] = mapped_column(String(10), nullable=False)
    estimated_quantity: Mapped[int] = mapped_column(Integer, default=0)
    actual_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    product = relationship("Product")
