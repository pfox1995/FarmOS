from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WORK_STAGES = Literal["사전준비", "경운", "파종", "정식", "작물관리", "수확"]


# ── 요청 ──


class JournalEntryCreate(BaseModel):
    """영농일지 생성 요청."""

    # 필수
    work_date: date
    field_name: str = Field(max_length=100)
    crop: str = Field(max_length=50)
    work_stage: WORK_STAGES

    # 선택 — 날씨
    weather: str | None = Field(default=None, max_length=20)

    # 선택 — 농약/비료 구입
    purchase_pesticide_type: str | None = Field(default=None, max_length=50)
    purchase_pesticide_product: str | None = Field(default=None, max_length=100)
    purchase_pesticide_amount: str | None = Field(default=None, max_length=50)
    purchase_fertilizer_type: str | None = Field(default=None, max_length=50)
    purchase_fertilizer_product: str | None = Field(default=None, max_length=100)
    purchase_fertilizer_amount: str | None = Field(default=None, max_length=50)

    # 선택 — 농약/비료 사용
    usage_pesticide_type: str | None = Field(default=None, max_length=50)
    usage_pesticide_product: str | None = Field(default=None, max_length=100)
    usage_pesticide_amount: str | None = Field(default=None, max_length=50)
    usage_fertilizer_type: str | None = Field(default=None, max_length=50)
    usage_fertilizer_product: str | None = Field(default=None, max_length=100)
    usage_fertilizer_amount: str | None = Field(default=None, max_length=50)

    # 선택 — 세부작업내용
    detail: str | None = None

    # 시스템
    raw_stt_text: str | None = None
    source: Literal["stt", "text", "auto"] = "text"


class JournalEntryUpdate(BaseModel):
    """영농일지 수정 요청. 보낸 필드만 업데이트."""

    work_date: date | None = None
    field_name: str | None = Field(default=None, max_length=100)
    crop: str | None = Field(default=None, max_length=50)
    work_stage: WORK_STAGES | None = None

    weather: str | None = Field(default=None, max_length=20)

    purchase_pesticide_type: str | None = Field(default=None, max_length=50)
    purchase_pesticide_product: str | None = Field(default=None, max_length=100)
    purchase_pesticide_amount: str | None = Field(default=None, max_length=50)
    purchase_fertilizer_type: str | None = Field(default=None, max_length=50)
    purchase_fertilizer_product: str | None = Field(default=None, max_length=100)
    purchase_fertilizer_amount: str | None = Field(default=None, max_length=50)

    usage_pesticide_type: str | None = Field(default=None, max_length=50)
    usage_pesticide_product: str | None = Field(default=None, max_length=100)
    usage_pesticide_amount: str | None = Field(default=None, max_length=50)
    usage_fertilizer_type: str | None = Field(default=None, max_length=50)
    usage_fertilizer_product: str | None = Field(default=None, max_length=100)
    usage_fertilizer_amount: str | None = Field(default=None, max_length=50)

    detail: str | None = None


# ── 응답 ──


class JournalEntryResponse(BaseModel):
    """영농일지 단건 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    work_date: date
    field_name: str
    crop: str
    work_stage: str

    weather: str | None = None

    purchase_pesticide_type: str | None = None
    purchase_pesticide_product: str | None = None
    purchase_pesticide_amount: str | None = None
    purchase_fertilizer_type: str | None = None
    purchase_fertilizer_product: str | None = None
    purchase_fertilizer_amount: str | None = None

    usage_pesticide_type: str | None = None
    usage_pesticide_product: str | None = None
    usage_pesticide_amount: str | None = None
    usage_fertilizer_type: str | None = None
    usage_fertilizer_product: str | None = None
    usage_fertilizer_amount: str | None = None

    detail: str | None = None
    raw_stt_text: str | None = None
    source: str

    created_at: datetime
    updated_at: datetime


class JournalEntryListResponse(BaseModel):
    """영농일지 목록 응답 (페이징 포함)."""

    items: list[JournalEntryResponse]
    total: int
    page: int
    page_size: int


# ── STT 파싱 ──


class STTParseRequest(BaseModel):
    """STT 텍스트 파싱 요청."""

    raw_text: str = Field(min_length=1, max_length=2000)


class STTParseResponse(BaseModel):
    """STT 텍스트 파싱 응답.

    한 번의 발화에 여러 작업이 섞여 있을 수 있어 entries 배열로 반환.
    단일 작업이면 entries 길이 1.
    """

    entries: list[dict] = []  # [{parsed, confidence, pesticide_match?}, ...]
    unparsed_text: str = ""
    rejected: bool = False
    reject_reason: str | None = None


# ── 누락 체크 + 일일 요약 ──


class MissingFieldItem(BaseModel):
    """누락 필드 항목."""

    entry_id: int
    field_name: str
    message: str
    work_date: str | None = None
    crop: str | None = None
    created_at: str | None = None


class DailySummaryResponse(BaseModel):
    """일일 영농 요약 응답."""

    date: str
    entry_count: int
    stages_worked: list[str]
    crops: list[str]
    weather: str | None = None
    missing_fields: list[MissingFieldItem]
    summary_text: str
