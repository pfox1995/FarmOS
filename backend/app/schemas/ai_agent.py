"""AI Agent Pydantic 스키마."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NutrientRatio(BaseModel):
    N: float = 1.0
    P: float = 1.0
    K: float = 1.0


class CropProfileIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, examples=["토마토"])
    growth_stage: str = Field(..., examples=["개화기"])
    optimal_temp: list[float] = Field(default=[20, 28], min_length=2, max_length=2)
    optimal_humidity: list[float] = Field(default=[60, 80], min_length=2, max_length=2)
    optimal_light_hours: float = Field(default=14, ge=0, le=24)
    nutrient_ratio: NutrientRatio = Field(default_factory=NutrientRatio)


class OverrideIn(BaseModel):
    control_type: str = Field(..., pattern="^(ventilation|irrigation|lighting|shading)$")
    values: dict
    reason: str = Field(default="수동 제어")


# ── agent-action-history (Design Ref §3.1, §4) ────────────────────────────────

ControlType = Literal["ventilation", "irrigation", "lighting", "shading"]
Priority = Literal["emergency", "high", "medium", "low"]
Source = Literal["rule", "llm", "tool", "manual"]
SummaryRange = Literal["today", "7d", "30d"]


class AIDecisionOut(BaseModel):
    """단건 decision 응답 shape. Relay/FarmOS 공통. Design §3.1"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    timestamp: datetime
    control_type: ControlType
    priority: Priority
    source: Source
    reason: str = ""
    action: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    sensor_snapshot: dict[str, Any] | None = None
    duration_ms: int | None = None
    created_at: datetime | None = None


class DecisionListOut(BaseModel):
    """목록 + (timestamp, id) 복합 keyset pagination 응답. Design §4.2"""

    items: list[AIDecisionOut]
    next_cursor: datetime | None = None
    next_cursor_id: str | None = None
    has_more: bool = False


class ActivitySummaryOut(BaseModel):
    """/activity/summary 응답. Design §4.1"""

    range: SummaryRange
    total: int
    by_control_type: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    avg_duration_ms: int | None = None
    latest_at: datetime | None = None
    generated_at: datetime


class DecisionCreateIn(BaseModel):
    """Bridge Worker 가 UPSERT 할 때 사용하는 입력 shape (module-3 에서 사용)."""

    id: str = Field(..., min_length=1, max_length=36)
    timestamp: datetime
    control_type: ControlType
    priority: Priority
    source: Source
    reason: str = ""
    action: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    sensor_snapshot: dict[str, Any] | None = None
    duration_ms: int | None = None
