from datetime import datetime
from sqlalchemy import Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week_start: Mapped[str] = mapped_column(String(10), nullable=False)
    week_end: Mapped[str] = mapped_column(String(10), nullable=False)
    total_revenue: Mapped[int] = mapped_column(Integer, default=0)
    total_expense: Mapped[int] = mapped_column(Integer, default=0)
    net_profit: Mapped[int] = mapped_column(Integer, default=0)
    report_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(default=func.now())
