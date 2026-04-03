from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class RevenueEntry(Base):
    __tablename__ = "revenue_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    product_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("products.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_price: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(20), default="sales")
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    order = relationship("Order", foreign_keys=[order_id])
    product = relationship("Product", foreign_keys=[product_id])
