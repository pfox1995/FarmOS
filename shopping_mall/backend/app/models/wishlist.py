from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from .user import User
    from .product import Product


class Wishlist(Base):
    __tablename__ = "shop_wishlists"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_shop_user_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_users.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_products.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="wishlists")
    product: Mapped["Product"] = relationship("Product")
