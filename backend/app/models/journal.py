from datetime import date, datetime, timezone

from sqlalchemy import Integer, String, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(10), ForeignKey("users.id"), nullable=False
    )

    # ── 필수 (농업ON ■) ──
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    crop: Mapped[str] = mapped_column(String(50), nullable=False)
    work_stage: Mapped[str] = mapped_column(String(20), nullable=False)

    # ── 선택 (농업ON □) ──
    weather: Mapped[str | None] = mapped_column(String(20), default=None)

    # 농약/비료 구입
    purchase_pesticide_type: Mapped[str | None] = mapped_column(
        String(50), default=None
    )
    purchase_pesticide_product: Mapped[str | None] = mapped_column(
        String(100), default=None
    )
    purchase_pesticide_amount: Mapped[str | None] = mapped_column(
        String(50), default=None
    )
    purchase_fertilizer_type: Mapped[str | None] = mapped_column(
        String(50), default=None
    )
    purchase_fertilizer_product: Mapped[str | None] = mapped_column(
        String(100), default=None
    )
    purchase_fertilizer_amount: Mapped[str | None] = mapped_column(
        String(50), default=None
    )

    # 농약/비료 사용
    usage_pesticide_type: Mapped[str | None] = mapped_column(String(50), default=None)
    usage_pesticide_product: Mapped[str | None] = mapped_column(
        String(100), default=None
    )
    usage_pesticide_amount: Mapped[str | None] = mapped_column(String(50), default=None)
    usage_fertilizer_type: Mapped[str | None] = mapped_column(String(50), default=None)
    usage_fertilizer_product: Mapped[str | None] = mapped_column(
        String(100), default=None
    )
    usage_fertilizer_amount: Mapped[str | None] = mapped_column(
        String(50), default=None
    )

    # 세부작업내용
    detail: Mapped[str | None] = mapped_column(Text, default=None)

    # ── 시스템 ──
    raw_stt_text: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[str] = mapped_column(String(10), default="text")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
