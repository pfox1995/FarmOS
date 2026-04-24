"""공익직불사업 (정부 지원금) API 엔드포인트.

Phase 1 — 결정적 REST 엔드포인트:
    GET  /subsidy/match             사용자 자격 매칭 (카드 목록용)
    POST /subsidy/ask               자연어 질의응답 (RAG + LLM)
    GET  /subsidy/detail/{code}     지원금 상세 정보 (드로어 UI)

Phase 2 (예정):
    POST /subsidy/chat              deep agent 기반 대화형 엔드포인트
    — 기존 /match, /ask 는 그대로 유지 (deterministic UI flow 용)
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.subsidy import (
    MatchResponse,
    SubsidyAskRequest,
    SubsidyAskResponse,
    SubsidyDetail,
)
from app.services.subsidy.prompts import SUBSIDY_SYSTEM_PROMPT, build_answer_prompt
from app.services.subsidy.tools import (
    get_subsidy_details,
    get_user_profile,
    list_eligible_subsidies,
    search_subsidy_regulations,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subsidy", tags=["subsidy"])


# ── 매칭 (카드 목록) ───────────────────────────────────────


@router.get("/match", response_model=MatchResponse)
async def match_subsidies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MatchResponse:
    """현재 사용자 프로필로 모든 지원금의 자격을 판정한다.

    반환: eligible / ineligible / needs_review 3 분류
    """
    profile = await get_user_profile(db, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="사용자 프로필을 찾을 수 없습니다.")
    return await list_eligible_subsidies(db, profile)


# ── 자연어 질의응답 (RAG + LLM) ──────────────────────────


@router.post("/ask", response_model=SubsidyAskResponse)
async def ask_subsidy(
    req: SubsidyAskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubsidyAskResponse:
    """시행지침에 대한 자연어 질문에 답변한다 (RAG + LLM)."""
    # 1. 시행지침 검색 (동기 Solar 임베딩·리랭커 호출 → asyncio.to_thread로 이벤트루프 보호)
    #    top_k=3: LLM 입력 토큰·처리시간 절감 (UI 에도 3건만 표시)
    citations = await asyncio.to_thread(search_subsidy_regulations, req.question, 3)
    if not citations:
        return SubsidyAskResponse(
            question=req.question,
            answer=(
                "죄송합니다. 이 질문에 대한 2026년도 기본형 공익직불사업 시행지침 조항을 "
                "찾지 못했습니다. 농관원(1334) 또는 지자체 담당자에게 문의해주세요."
            ),
            citations=[],
            escalation_needed=True,
        )

    # 2. 사용자 프로필 요약 (답변 개인화용)
    profile = await get_user_profile(db, user.id)
    profile_summary = _format_profile_summary(profile) if profile else None

    # 3. 인용 조항 텍스트 구성
    citations_text = "\n\n".join(
        f"[인용 {i + 1}] {c.chapter} > {c.article}\n{c.snippet}"
        for i, c in enumerate(citations)
    )

    # 4. LLM 호출 (OpenRouter 직결, google/gemma-4-31b-it)
    user_prompt = build_answer_prompt(
        question=req.question,
        citations_text=citations_text,
        profile_summary=profile_summary,
    )
    try:
        answer = await _call_llm(SUBSIDY_SYSTEM_PROMPT, user_prompt)
    except RuntimeError as e:
        # 우리 쪽 설정 누락 (예: LITELLM_API_KEY 미설정) — 배포/운영 버그
        logger.error(f"LLM 설정 오류: {e}")
        raise HTTPException(status_code=500, detail=f"서버 설정 오류: {e}") from e
    except (
        AuthenticationError,
        PermissionDeniedError,
        BadRequestError,
        NotFoundError,
    ) as e:
        # 업스트림이 우리 요청을 거절 — 모델명/키/권한 설정이 틀렸다는 뜻.
        # 재시도해도 똑같이 실패하므로 503 이 아니라 502 (Bad Gateway) 로 표시한다.
        logger.error(f"LLM 설정/요청 오류 ({type(e).__name__}): {e}")
        raise HTTPException(
            status_code=502,
            detail=(
                f"LLM 공급자가 요청을 거절했습니다. 설정을 확인하세요 "
                f"({type(e).__name__} {getattr(e, 'status_code', '?')}: {str(e)[:200]})"
            ),
        ) from e
    except (
        APITimeoutError,
        APIConnectionError,
        RateLimitError,
        InternalServerError,
    ) as e:
        # 일시적 장애 (네트워크 끊김, 상류 5xx, 레이트리밋). 재시도 가치 있음.
        # 타임아웃은 504, 그 외는 503. 레이트리밋이면 Retry-After 안내 포함.
        logger.warning(f"LLM 일시 장애 ({type(e).__name__}): {e}")
        status = 504 if isinstance(e, APITimeoutError) else 503
        headers = {"Retry-After": "5"} if isinstance(e, RateLimitError) else None
        raise HTTPException(
            status_code=status,
            detail="답변 생성 중 일시적 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            headers=headers,
        ) from e
    except APIStatusError as e:
        # 위에서 못 잡은 기타 HTTP 에러. status_code 그대로 전파해 계층 혼동을 줄인다.
        logger.error(f"LLM HTTP {e.status_code}: {e}")
        raise HTTPException(
            status_code=502 if e.status_code < 500 else 503,
            detail="답변 생성 중 상류 오류가 발생했습니다.",
        ) from e
    except Exception as e:
        # 정말 예상 못한 에러. 503 으로 숨기지 말고 500 으로 드러낸다.
        logger.exception(f"LLM 호출 중 예상 못한 오류: {e}")
        raise HTTPException(status_code=500, detail="내부 오류") from e

    return SubsidyAskResponse(
        question=req.question,
        answer=answer,
        citations=citations,
        escalation_needed=False,
    )


# ── 지원금 상세 (드로어 UI) ──────────────────────────────


@router.get("/detail/{subsidy_code}", response_model=SubsidyDetail)
async def get_detail(
    subsidy_code: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubsidyDetail:
    """지원금 코드로 상세 정보 조회."""
    detail = await get_subsidy_details(db, subsidy_code)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"지원금 '{subsidy_code}'를 찾을 수 없습니다.")
    return detail


# ── 내부 헬퍼 ──────────────────────────────────────────────


def _format_profile_summary(profile) -> str:
    """사용자 프로필을 LLM에 전달할 자연어 요약으로 변환."""
    parts: list[str] = [f"경작 면적 {profile.area_ha}ha"]
    if profile.farmland_type:
        parts.append(f"농지 유형 {profile.farmland_type}")
    parts.append("진흥지역" if profile.is_promotion_area else "비진흥지역")
    parts.append("농업경영체 등록 완료" if profile.has_farm_registration else "경영체 미등록")
    parts.append(f"영농 경력 {profile.years_farming}년")
    parts.append(f"농촌 거주 {profile.years_rural_residence}년")
    if profile.farmer_type and profile.farmer_type != "일반":
        parts.append(f"{profile.farmer_type} 농업인")
    return ", ".join(parts)


async def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """공익직불 전용 LLM 호출. LiteLLM 프록시 경유 (팀 API 사용량 통합 추적).

    설정 노트:
      - settings.LITELLM_API_KEY / settings.LITELLM_URL 사용
      - async with httpx.AsyncClient 로 커넥션 누수 방지
      - reasoning 파라미터는 전달하지 않는다. gpt-5-nano 처럼 effort="minimal" 을
        존중하는 모델도 있지만, gemma-4-31b-it (Venice provider) 는 무시하고
        500+ reasoning 토큰을 생성해 max_tokens 예산을 잠식해 빈 응답을 반환한다
        (finish_reason=length). 모델을 바꾸기 전엔 reasoning 옵션을 끄는 것이 안전.

    속도 튜닝:
      - max_tokens=500: 장문 답변의 꼬리 지연 제거 (시행지침 Q&A 는 3~5 문장이면 충분)
      - temperature=0.2: 인용 기반 답변이므로 낮은 온도가 일관성·속도에 유리
    """
    api_key = settings.LITELLM_API_KEY
    if not api_key:
        raise RuntimeError(
            "LITELLM_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    async with httpx.AsyncClient(
        http1=True,
        http2=False,
        timeout=httpx.Timeout(60.0, connect=20.0),
    ) as http_client:
        llm = ChatOpenAI(
            model=settings.SUBSIDY_LLM_MODEL,
            base_url=settings.LITELLM_URL,
            api_key=api_key,
            temperature=0.2,
            max_tokens=500,
            http_async_client=http_client,
        )
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
    content = response.content
    if not isinstance(content, str) or not content.strip():
        # 빈 응답은 성공처럼 보여도 사용자에겐 실패. 상위 핸들러가 502 로 분류하도록 예외화.
        meta = getattr(response, "response_metadata", {}) or {}
        finish = meta.get("finish_reason", "unknown")
        usage = meta.get("token_usage", {})
        raise RuntimeError(
            f"LLM 이 빈 응답을 반환했습니다 (finish_reason={finish}, usage={usage}). "
            f"모델 설정이나 max_tokens 를 확인하세요."
        )
    return content
