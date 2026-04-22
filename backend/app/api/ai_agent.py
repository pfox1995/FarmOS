"""AI Agent Action History API.

Design Ref: §4 API Specification — FarmOS 미러 테이블에서 요약/목록(cursor)/단건 상세를 제공한다.
Plan SC: SC-2, SC-3, SC-4, SC-5 커버.

Bridge Worker (module-3) 가 Relay 의 원본을 `ai_agent_decisions` + `ai_agent_activity_*` 로 적재한 뒤,
본 라우터가 읽기 전용으로 제공한다. Bridge 비활성화 상태에서도 API 자체는 빈 결과를 반환하며
동작한다 (AI_AGENT_BRIDGE_ENABLED=False 기본).
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.ai_agent import (
    AiAgentActivityDaily,
    AiAgentActivityHourly,
    AiAgentDecision,
)
from app.models.user import User
from app.schemas.ai_agent import (
    ActivitySummaryOut,
    AIDecisionOut,
    DecisionListOut,
    SummaryRange,
)

router = APIRouter(prefix="/ai-agent", tags=["ai-agent"])


# ── 내부 유틸 ──────────────────────────────────────────────────────────────────


def _range_start(range_key: SummaryRange, now: datetime, tz: ZoneInfo) -> datetime:
    """range 키를 시작 UTC datetime 으로 환산. tz 기준 로컬 자정을 UTC 로 변환."""
    local_now = now.astimezone(tz)
    if range_key == "today":
        local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_key == "7d":
        local_start = (local_now - timedelta(days=6)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif range_key == "30d":
        local_start = (local_now - timedelta(days=29)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_RANGE", "message": "range must be one of today|7d|30d"},
        )
    return local_start.astimezone(timezone.utc)


def _merge_counter(dst: dict[str, int], src: Any) -> None:
    """JSONB 카운터 dict 를 dst 에 누적 병합."""
    if not isinstance(src, dict):
        return
    for key, val in src.items():
        try:
            dst[key] = dst.get(key, 0) + int(val)
        except (TypeError, ValueError):
            continue


# ── 4.1 GET /activity/summary ─────────────────────────────────────────────────


@router.get(
    "/activity/summary",
    response_model=ActivitySummaryOut,
    dependencies=[Depends(get_current_user)],
)
async def get_activity_summary(
    range_key: SummaryRange = Query(default="today", alias="range"),
    db: AsyncSession = Depends(get_db),
) -> ActivitySummaryOut:
    """오늘/7일/30일 집계. ai_agent_activity_daily 에서 GROUP BY 후 후처리로 by_* 병합."""
    tz = ZoneInfo(settings.APP_TIMEZONE)
    now = datetime.now(timezone.utc)
    start = _range_start(range_key, now, tz)
    start_date = start.astimezone(tz).date()

    rows = (
        await db.execute(
            select(AiAgentActivityDaily).where(AiAgentActivityDaily.day >= start_date)
        )
    ).scalars().all()

    total = 0
    by_control_type: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    # 정확한 평균을 위해 duration_sum / duration_count 를 직접 누적한다.
    # avg_duration_ms 는 행별 캐시일 뿐이고 가중치를 r.count(전체 행 수) 로 두면
    # null-duration 행이 다시 포함되는 편향이 발생하므로 사용하지 않는다.
    duration_total_sum = 0
    duration_total_count = 0
    latest_at: datetime | None = None

    for r in rows:
        total += r.count
        by_control_type[r.control_type] = by_control_type.get(r.control_type, 0) + r.count
        _merge_counter(by_source, r.by_source)
        _merge_counter(by_priority, r.by_priority)
        if r.duration_count > 0:
            duration_total_sum += r.duration_sum
            duration_total_count += r.duration_count
        if r.last_at is not None and (latest_at is None or r.last_at > latest_at):
            latest_at = r.last_at

    avg_duration = (
        round(duration_total_sum / duration_total_count)
        if duration_total_count > 0
        else None
    )

    return ActivitySummaryOut(
        range=range_key,
        total=total,
        by_control_type=by_control_type,
        by_source=by_source,
        by_priority=by_priority,
        avg_duration_ms=avg_duration,
        latest_at=latest_at,
        generated_at=now,
    )


# ── 4.2 GET /decisions (cursor pagination) ────────────────────────────────────


@router.get(
    "/decisions",
    response_model=DecisionListOut,
    dependencies=[Depends(get_current_user)],
)
async def list_decisions(
    cursor: datetime | None = Query(default=None, description="timestamp < cursor (ISO8601)"),
    cursor_id: str | None = Query(
        default=None,
        max_length=36,
        description="composite tiebreaker: id < cursor_id when timestamp = cursor",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    control_type: str | None = Query(default=None, pattern="^(ventilation|irrigation|lighting|shading)$"),
    source: str | None = Query(default=None, pattern="^(rule|llm|tool|manual)$"),
    priority: str | None = Query(default=None, pattern="^(emergency|high|medium|low)$"),
    since: datetime | None = Query(default=None, description="timestamp >= since"),
    until: datetime | None = Query(default=None, description="timestamp <= until"),
    db: AsyncSession = Depends(get_db),
) -> DecisionListOut:
    """최신순 (timestamp, id) 복합 keyset pagination. limit+1 을 fetch 해 has_more 판정.

    정렬·cursor·필터 모두 timestamp(이벤트 시각) + id 기준으로 통일하여
    동일 timestamp 다중 행에서의 누락/중복을 방지한다.
    """
    conds = []
    if cursor is not None:
        if cursor_id is not None:
            conds.append(
                or_(
                    AiAgentDecision.timestamp < cursor,
                    and_(
                        AiAgentDecision.timestamp == cursor,
                        AiAgentDecision.id < cursor_id,
                    ),
                )
            )
        else:
            conds.append(AiAgentDecision.timestamp < cursor)
    if control_type is not None:
        conds.append(AiAgentDecision.control_type == control_type)
    if source is not None:
        conds.append(AiAgentDecision.source == source)
    if priority is not None:
        conds.append(AiAgentDecision.priority == priority)
    if since is not None:
        conds.append(AiAgentDecision.timestamp >= since)
    if until is not None:
        conds.append(AiAgentDecision.timestamp <= until)

    stmt = select(AiAgentDecision)
    if conds:
        stmt = stmt.where(and_(*conds))
    stmt = stmt.order_by(
        AiAgentDecision.timestamp.desc(), AiAgentDecision.id.desc()
    ).limit(limit + 1)

    rows = (await db.execute(stmt)).scalars().all()

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = items[-1].timestamp if has_more and items else None
    next_cursor_id = items[-1].id if has_more and items else None

    return DecisionListOut(
        items=[AIDecisionOut.model_validate(r) for r in items],
        next_cursor=next_cursor,
        next_cursor_id=next_cursor_id,
        has_more=has_more,
    )


# ── 4.3 GET /decisions/{id} ───────────────────────────────────────────────────


@router.get(
    "/decisions/{decision_id}",
    response_model=AIDecisionOut,
    dependencies=[Depends(get_current_user)],
)
async def get_decision_detail(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
) -> AIDecisionOut:
    """단건 상세 조회. 30일 TTL 로 정리된 경우 404."""
    if not decision_id or len(decision_id) > 36:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_ID", "message": "decision_id must be 1-36 chars"},
        )

    row = (
        await db.execute(
            select(AiAgentDecision).where(AiAgentDecision.id == decision_id)
        )
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DECISION_NOT_FOUND",
                "message": "해당 판단을 찾을 수 없습니다. 삭제되었거나 30일이 지났을 수 있습니다.",
            },
        )

    return AIDecisionOut.model_validate(row)


# ── 보조: 최근 N 시간 그래프 (Design §5 의 선택적 용도) ────────────────────────


@router.get(
    "/activity/hourly",
    dependencies=[Depends(get_current_user)],
)
async def get_activity_hourly(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """최근 N 시간(기본 24) 시간별 집계. 그래프 데이터용."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=hours - 1)).replace(minute=0, second=0, microsecond=0)

    rows = (
        await db.execute(
            select(
                AiAgentActivityHourly.hour,
                AiAgentActivityHourly.control_type,
                func.sum(AiAgentActivityHourly.count).label("count"),
            )
            .where(AiAgentActivityHourly.hour >= start)
            .group_by(AiAgentActivityHourly.hour, AiAgentActivityHourly.control_type)
            .order_by(AiAgentActivityHourly.hour.asc())
        )
    ).all()

    return [
        {
            "hour": r.hour.isoformat(),
            "control_type": r.control_type,
            "count": int(r.count or 0),
        }
        for r in rows
    ]


# ── Bridge 헬스 상태 (운영 가시성) ───────────────────────────────────────────


@router.get("/bridge/status", dependencies=[Depends(get_current_user)])
async def get_bridge_status(request: Request) -> dict[str, Any]:
    """Bridge Worker 상태 조회. AI_AGENT_BRIDGE_ENABLED=False 이면 disabled 로 응답."""
    if not settings.AI_AGENT_BRIDGE_ENABLED:
        return {
            "enabled": False,
            "healthy": False,
            "message": "AI_AGENT_BRIDGE_ENABLED=False (Relay patch 미적용 또는 수동 비활성화)",
        }

    bridge = getattr(request.app.state, "ai_agent_bridge", None)
    if bridge is None:
        return {
            "enabled": True,
            "healthy": False,
            "message": "Bridge 인스턴스가 초기화되지 않음 (기동 실패 가능성)",
        }

    return {
        "enabled": True,
        "healthy": bridge.healthy,
        "last_event_at": bridge.last_event_at.isoformat() if bridge.last_event_at else None,
        "last_backfill_at": bridge.last_backfill_at.isoformat() if bridge.last_backfill_at else None,
        "last_error": bridge.last_error,
        "total_processed": bridge.total_processed,
        "relay_base_url": settings.IOT_RELAY_BASE_URL,
    }
