"""AI Agent decision 원본 미러 + 요약 테이블.

Design Ref: §3.3 Database Schema — Relay 에서 FarmOS 로 SSE Bridge 로 수신된 decisions 를
원본(`ai_agent_decisions`, 30일 TTL) + 일/시간 요약(`ai_agent_activity_daily/hourly`) 로 적재한다.
"""

from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, String, Text, desc
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class AiAgentDecision(Base):
    """AI Agent 판단 원본 미러. id 는 Relay 가 생성한 UUID 를 그대로 재사용한다."""

    __tablename__ = "ai_agent_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    control_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    action: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tool_calls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sensor_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc, index=True
    )

    # list_decisions 쿼리 패턴 (control_type/source 필터 + timestamp DESC 정렬) 가속용
    # 복합 인덱스. timestamp 는 DESC 로 두어 ORDER BY timestamp DESC 와 정렬 일치.
    __table_args__ = (
        Index(
            "ix_ai_agent_decisions_control_source_timestamp",
            "control_type",
            "source",
            desc("timestamp"),
        ),
    )


class AiAgentActivityDaily(Base):
    """일별 집계. (day, control_type) 복합 PK. Bridge Worker 가 UPSERT 로 증분 갱신."""

    __tablename__ = "ai_agent_activity_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    control_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    by_source: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    by_priority: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # avg_duration_ms 는 (duration_sum / duration_count) 의 반올림 캐시.
    # null-duration 행은 분모/분자에서 모두 제외되어 편향이 없다.
    avg_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_sum: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )


class AiAgentActivityHourly(Base):
    """시간별 집계. (hour, control_type) 복합 PK. hour 는 date_trunc('hour', timestamp)."""

    __tablename__ = "ai_agent_activity_hourly"

    hour: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    control_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    by_source: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    by_priority: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now_utc
    )
