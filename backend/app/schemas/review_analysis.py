"""리뷰 분석 Pydantic 스키마.

# Design Ref: §4, §5.1 — API 요청/응답 스키마
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 공통 서브모델
# ---------------------------------------------------------------------------

class SentimentSummary(BaseModel):
    positive: int = 0
    negative: int = 0
    neutral: int = 0
    total: int = 0


class KeywordItem(BaseModel):
    word: str
    count: int
    sentiment: str  # "positive" | "negative" | "neutral"


class SummaryData(BaseModel):
    overall: str = ""
    positives: list[str] = []
    negatives: list[str] = []
    suggestions: list[str] = []


class SentimentResult(BaseModel):
    id: str
    sentiment: str
    score: float = Field(ge=-1.0, le=1.0)
    reason: str = ""


class AnomalyAlert(BaseModel):
    week: str = ""
    type: str = ""
    value: float = 0.0
    expected: float = 0.0
    deviation: float = 0.0
    message: str = ""


class TrendData(BaseModel):
    week: str
    positive: int = 0
    negative: int = 0
    neutral: int = 0
    total: int = 0
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    neutral_ratio: float = 0.0


class SearchResult(BaseModel):
    id: str
    text: str
    similarity: float
    metadata: dict = {}


# ---------------------------------------------------------------------------
# API 요청 스키마
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """POST /api/v1/reviews/analyze 요청."""
    scope: str = "all"
    analysis_types: list[str] = ["sentiment", "keywords", "summary"]
    batch_size: int = Field(default=20, ge=5, le=50)


class SearchRequest(BaseModel):
    """POST /api/v1/reviews/search 요청."""
    query: str
    top_k: int = Field(default=10, ge=1, le=50)
    filters: SearchFilters | None = None


class SearchFilters(BaseModel):
    platform: str | None = None
    rating_min: int | None = Field(default=None, ge=1, le=5)
    rating_max: int | None = Field(default=None, ge=1, le=5)
    date_from: str | None = None
    date_to: str | None = None


class EmbedRequest(BaseModel):
    """POST /api/v1/reviews/embed 요청."""
    source: str = "mock"  # "mock" | "db"


class AnalysisSettingsUpdate(BaseModel):
    """PUT /api/v1/reviews/settings 요청."""
    auto_batch_enabled: bool | None = None
    batch_trigger_count: int | None = Field(default=None, ge=1, le=100)
    batch_schedule: str | None = None
    default_batch_size: int | None = Field(default=None, ge=5, le=50)


# ---------------------------------------------------------------------------
# API 응답 스키마
# ---------------------------------------------------------------------------

class AnalyzeResponse(BaseModel):
    """POST /api/v1/reviews/analyze 응답."""
    analysis_id: int
    status: str  # "completed" | "failed"
    review_count: int
    sentiment_summary: SentimentSummary
    keywords: list[KeywordItem]
    summary: SummaryData
    anomalies: list[AnomalyAlert] = []
    processing_time_ms: int
    llm_provider: str
    llm_model: str


class SearchResponse(BaseModel):
    """POST /api/v1/reviews/search 응답."""
    results: list[SearchResult]
    total: int


class TrendsResponse(BaseModel):
    """GET /api/v1/reviews/trends 응답."""
    trends: list[TrendData]
    anomalies: list[AnomalyAlert] = []


class EmbedResponse(BaseModel):
    """POST /api/v1/reviews/embed 응답."""
    embedded_count: int
    total_count: int
    source: str


class AnalysisSettings(BaseModel):
    """GET /api/v1/reviews/settings 응답."""
    auto_batch_enabled: bool = False
    batch_trigger_count: int = 10
    batch_schedule: str | None = None
    default_batch_size: int = 20


class AnalysisListItem(BaseModel):
    """GET /api/v1/reviews/analysis 리스트 아이템."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_type: str
    target_scope: str
    review_count: int
    sentiment_summary: SentimentSummary | dict | None = None
    processing_time_ms: int
    llm_provider: str | None = None
    created_at: str | None = None
