from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Text, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ChatSession(Base):
    __tablename__ = "shop_chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    # Ensure only one active session per user (partial unique index)
    __table_args__ = (
        Index(
            "idx_user_active_session",
            user_id,
            unique=True,
            postgresql_where="status = 'active'",
        ),
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 확인 대기 중인 액션을 JSON 문자열로 저장 (예: 교환 신청 대기)
    # {"type": "exchange_request", "exchange_request_id": 42, "summary": "..."}
    pending_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    logs = relationship("ChatLog", back_populates="session")
