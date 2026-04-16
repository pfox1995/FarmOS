from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ExchangeRequest(Base):
    __tablename__ = "shop_exchange_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_users.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_orders.id"), nullable=False)
    order_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("shop_order_items.id"), nullable=True
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # pending_confirm → confirmed → processing → completed | cancelled
    status: Mapped[str] = mapped_column(String(30), default="pending_confirm", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user = relationship("User")
    order = relationship("Order")
