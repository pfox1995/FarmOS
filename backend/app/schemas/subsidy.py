"""공익직불 관련 Pydantic 스키마.

Tool 입출력과 API 응답에 모두 사용됩니다.
Phase 2 (deep agent)에서도 동일한 스키마를 도구 시그니처로 재사용하므로
여기서 타입을 견고하게 정의해두면 마이그레이션 비용이 크게 줄어듭니다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ── 사용자 프로필 (User 모델에서 추출) ────────────────────────


class UserProfile(BaseModel):
    """자격 판정에 필요한 사용자 농업 정보. User 모델의 투영."""

    user_id: str
    location: str = ""
    area_ha: float = Field(default=0.0, description="경작 면적 (ha)")
    main_crop: str = ""
    farmland_type: str = Field(default="", description="논/밭/과수 등")
    is_promotion_area: bool = False
    has_farm_registration: bool = False
    farmer_type: str = Field(default="일반", description="일반/청년/후계/귀농 등")
    years_rural_residence: int = 0
    years_farming: int = 0


# ── 지원금 정보 ────────────────────────────────────────────


class SubsidyCard(BaseModel):
    """카드 목록용 요약 정보."""

    id: int
    code: str
    name_ko: str
    category: str
    description: str
    estimated_amount_krw: int | None = Field(
        default=None, description="예상 연간 수령액 (면적/구간 적용 후)"
    )
    source_articles: list[str] = []


class SubsidyDetail(BaseModel):
    """상세 보기용 전체 정보."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name_ko: str
    category: str
    description: str
    min_area_ha: float
    max_area_ha: float | None
    requires_promotion_area: bool | None
    requires_farm_registration: bool
    min_rural_residence_years: int
    min_farming_years: int
    eligible_farmland_types: list[str]
    eligible_farmer_types: list[str]
    payment_structure: dict
    source_articles: list[str]
    payment_amount_krw: int | None


# ── 자격 판정 결과 ─────────────────────────────────────────


class Reason(BaseModel):
    """판정 사유 한 줄 + 근거 조항 태그.

    `source` 는 시행지침 소단원 식별자 (예: "II-3", "II-3 ⑤").
    UI 에서 reason 옆에 작은 chip 으로 표시되어 사용자가 근거를 추적할 수 있게 한다.
    None 일 경우 UI 는 chip 을 숨긴다 (집계성 메시지 등).
    """

    text: str
    source: str | None = None


class SourceClause(BaseModel):
    """판정에 인용된 시행지침 소단원의 (태그, 본문) 쌍.

    예: tag="II-3 ⑤", text="신청자 개인 농업 외 종합소득 2,000만원 미만".
    EligibilityResult.reasons 에 등장한 source 태그 중 unique 한 것만 채워진다.
    """

    tag: str
    text: str


class PaymentStep(BaseModel):
    """지급액 계산의 한 줄 (fixed 의 경우 1줄, tiered 는 구간별 N줄)."""

    description: str
    amount_krw: int


class PaymentCalculation(BaseModel):
    """예상 수령액의 계산 내역.

    - fixed 지급: steps 에 "정액 지급" 한 줄, note 로 면적 무관 설명.
    - tiered_by_area: steps 에 각 면적구간별 계산 한 줄씩, note 로 구간 정책 설명.
    """

    total_krw: int
    steps: list[PaymentStep] = []
    note: str | None = None


class EligibilityResult(BaseModel):
    """단일 지원금에 대한 자격 판정 결과."""

    subsidy_code: str
    subsidy_name: str
    status: Literal["eligible", "ineligible", "needs_review"]
    reasons: list[Reason] = Field(
        default_factory=list,
        description="해당/비해당 사유 (사용자 안내용, 각 항목은 근거 조항 태그 포함 가능)",
    )
    estimated_amount_krw: int | None = None
    source_articles: list[str] = []
    source_clauses: list[SourceClause] = Field(
        default_factory=list,
        description="판정에 실제 인용된 시행지침 소단원 (tag, 본문) — 출처 섹션 표시용",
    )
    payment_calculation: PaymentCalculation | None = Field(
        default=None,
        description="예상 수령액 계산 내역 — eligible/needs_review 에서만 채워짐",
    )


class MatchResponse(BaseModel):
    """규칙 기반 매칭 전체 응답."""

    user_id: str
    eligible: list[EligibilityResult] = []
    ineligible: list[EligibilityResult] = []
    needs_review: list[EligibilityResult] = []


# ── RAG 질의응답 ─────────────────────────────────────────────


class SubsidyAskRequest(BaseModel):
    question: str = Field(
        min_length=2,
        max_length=500,
        description="예: '내가 청년농인데 받을 수 있는 직불금은?'",
    )
    subsidy_code: str | None = Field(
        default=None, description="특정 지원금에 한정한 질문인 경우",
    )


class Citation(BaseModel):
    """답변의 근거가 된 시행지침 조항 인용.

    시행지침서(guideline manual)는 법령이 아니므로 '제X조 제Y항' 구조가 없고,
    'CHAPTER N > Roman > Arabic' 계층으로 주제가 조직됨.
    """

    article: str = Field(
        description="소단원 제목 (예: '3. 소농직불 지급대상 자격요건')"
    )
    chapter: str = Field(
        default="",
        description="상위 계층 경로 (예: 'CHAPTER 1 > II. 기본직불금 지급대상 자격요건 등 주요 내용')",
    )
    snippet: str = Field(description="해당 소단원 본문 일부")
    similarity: float = Field(description="리랭커 점수 (상대적 순위용, 0~1 정규화 아님)")


class SubsidyAskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation] = []
    escalation_needed: bool = Field(
        default=False,
        description="시행지침으로 답할 수 없어 상담 필요시 True",
    )


# ── 청크 메타데이터 (chunker/RAG 내부용) ──────────────────────


class ChunkMetadata(BaseModel):
    """ChromaDB 청크에 저장되는 메타데이터."""

    section_type: Literal["조", "별표", "서식", "부칙", "기타"] = "조"
    chapter: str = ""
    section: str = ""
    article: str = ""
    article_title: str = ""
    subsidy_tags: list[str] = Field(
        default_factory=list,
        description="해당 청크가 관련된 지원금 코드 (sub-agent 필터링용)",
    )
