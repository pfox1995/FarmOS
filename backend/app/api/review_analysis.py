"""리뷰 분석 API 라우터.

# Design Ref: §4 — API Design
# Plan SC: SC-01~SC-07 통합

엔드포인트:
    POST /api/v1/reviews/analyze       분석 실행 (수동)
    GET  /api/v1/reviews/analysis      최신 분석 결과 조회
    POST /api/v1/reviews/search        RAG 의미 검색
    GET  /api/v1/reviews/trends        트렌드/이상 탐지
    GET  /api/v1/reviews/report/pdf    PDF 리포트 다운로드
    POST /api/v1/reviews/embed         리뷰 임베딩 저장
    GET  /api/v1/reviews/settings      자동 분석 설정 조회
    PUT  /api/v1/reviews/settings      자동 분석 설정 변경
"""

import asyncio
import json
import logging
import random

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.core.review_rag import ReviewRAG
from app.core.review_analyzer import ReviewAnalyzer
from app.core.trend_detector import TrendDetector
from app.core.review_report import ReviewReportGenerator
from app.models.review_analysis import ReviewAnalysis
from app.schemas.review_analysis import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalysisSettings,
    AnalysisSettingsUpdate,
    AnalysisListItem,
    AnomalyAlert,
    EmbedRequest,
    EmbedResponse,
    KeywordItem,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SentimentSummary,
    SummaryData,
    TrendData,
    TrendsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["review-analysis"])

# 서비스 인스턴스 (싱글턴)
_rag = ReviewRAG()
_analyzer = ReviewAnalyzer()
_trend_detector = TrendDetector()
_report_generator = ReviewReportGenerator()

# 인메모리 설정 (추후 DB로 이동 가능)
_settings = AnalysisSettings()


async def _get_seller_product_ids(db: AsyncSession, seller_id: str | None = None) -> list[int] | None:
    """판매자의 상품 ID 목록 조회 (멀티테넌트).

    현재 shop_stores에 owner_id 컬럼이 없으므로 항상 None(전체 접근)을 반환합니다.
    향후 owner_id가 추가되면 아래 주석 해제하여 필터링을 활성화합니다.

    Args:
        db: AsyncSession
        seller_id: 판매자 ID (None이면 전체 접근)

    Returns:
        상품 ID 리스트 (None이면 전체 접근)
    """
    if seller_id is None:
        return None

    # TODO: shop_stores에 owner_id 추가 후 아래 코드 활성화
    # from sqlalchemy import text as sa_text
    # result = await db.execute(
    #     sa_text("""
    #         SELECT p.id FROM shop_products p
    #         JOIN shop_stores s ON p.store_id = s.id
    #         WHERE s.owner_id = :seller_id
    #     """),
    #     {"seller_id": seller_id},
    # )
    # product_ids = [row[0] for row in result.fetchall()]
    # return product_ids if product_ids else None

    return None  # 현재는 전체 접근


def _stratified_sample(reviews: list[dict], sample_size: int) -> list[dict]:
    """rating별 비례 층화 샘플링으로 대표성 있는 부분집합을 추출합니다.

    전체 10,000건 중 rating 분포를 유지하면서 sample_size건만 추출합니다.
    예: 전체에서 5점이 60%, 1점이 5%면 샘플에서도 동일 비율.
    """
    if len(reviews) <= sample_size:
        return reviews

    # rating별 그룹핑
    by_rating: dict[int, list[dict]] = {}
    for r in reviews:
        key = int(r.get("metadata", {}).get("rating", r.get("rating", 0)))
        by_rating.setdefault(key, []).append(r)

    sampled: list[dict] = []
    total = len(reviews)
    for rating, group in by_rating.items():
        # 비례 배분 (최소 1건)
        n = max(1, round(len(group) / total * sample_size))
        sampled.extend(random.sample(group, min(n, len(group))))

    # 목표 수에 맞추기 (반올림 오차 보정)
    if len(sampled) > sample_size:
        sampled = random.sample(sampled, sample_size)
    elif len(sampled) < sample_size:
        remaining = [r for r in reviews if r not in sampled]
        extra = min(sample_size - len(sampled), len(remaining))
        sampled.extend(random.sample(remaining, extra))

    return sampled


# ---------------------------------------------------------------------------
# POST /reviews/embed — 리뷰 임베딩 저장
# ---------------------------------------------------------------------------

@router.post("/embed", response_model=EmbedResponse)
async def embed_reviews(
    req: EmbedRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """리뷰 데이터를 ChromaDB에 임베딩 저장합니다.

    shop_reviews 테이블에서 리뷰를 조회하여 ChromaDB에 동기화합니다.
    seller_id가 지정되면 해당 판매자의 상품 리뷰만 동기화합니다.
    """
    added = await _rag.sync_from_db(db)
    total = _rag.get_count()
    return EmbedResponse(embedded_count=added, total_count=total, source="db")


@router.get("/embed/stream")
async def embed_reviews_stream(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """SSE로 DB 리뷰 임베딩 진행률을 스트리밍합니다."""

    async def event_generator():
        async for update in _rag.sync_from_db_chunked(db, chunk_size=100):
            yield {"data": json.dumps(update, ensure_ascii=False)}
            await asyncio.sleep(0)

    return EventSourceResponse(event_generator())


@router.get("/analyze/stream")
async def analyze_reviews_stream(
    batch_size: int = Query(50, ge=5, le=100),
    sample_size: int = Query(200, ge=50, le=10000, description="분석할 리뷰 샘플 수 (층화 샘플링)"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """SSE로 분석 진행률을 스트리밍합니다.

    전체 리뷰 중 sample_size건을 층화 샘플링하여 분석합니다.
    rating 분포를 유지하므로 통계적 대표성이 보장됩니다.
    """

    async def event_generator():
        # 임베딩 없으면 DB에서 자동 동기화
        if _rag.get_count() == 0:
            yield {"data": json.dumps({"progress": 0, "message": "DB 리뷰 임베딩 중..."}, ensure_ascii=False)}
            await _rag.sync_from_db(db)

        reviews = _rag.get_all_reviews()
        if not reviews:
            yield {"data": json.dumps({"progress": 100, "error": "분석할 리뷰가 없습니다."}, ensure_ascii=False)}
            return

        total_count = len(reviews)

        # 층화 샘플링: rating 비율을 유지하면서 sample_size건 추출
        sampled = _stratified_sample(reviews, sample_size)

        yield {"data": json.dumps({
            "progress": 0,
            "message": f"전체 {total_count}건 중 {len(sampled)}건 샘플링 → 분석 시작",
        }, ensure_ascii=False)}

        analysis_reviews = [
            {"id": r["id"], "text": r["text"], "rating": r["metadata"].get("rating", 0),
             "platform": r["metadata"].get("platform", ""), "date": r["metadata"].get("date", "")}
            for r in sampled
        ]

        final_result = None
        async for update in _analyzer.analyze_batch_with_progress(analysis_reviews, batch_size=batch_size):
            if "result" in update:
                final_result = update["result"]
            yield {"data": json.dumps(
                {k: v for k, v in update.items() if k != "result"},
                ensure_ascii=False,
            )}
            await asyncio.sleep(0)

        # DB 저장 (review_count는 전체 수 기록)
        if final_result:
            summary_data = final_result.get("summary", {})
            trends = _trend_detector.calculate_weekly_trends([
                {**s, "date": next((r["date"] for r in analysis_reviews if str(r["id"]) == str(s.get("id"))), "")}
                for s in final_result.get("sentiments", [])
            ])
            anomalies = _trend_detector.detect_anomalies(trends)

            analysis_record = ReviewAnalysis(
                analysis_type="manual", target_scope="all",
                review_count=total_count,
                sentiment_summary=final_result.get("sentiment_summary"),
                keywords=final_result.get("keywords", []),
                summary=json.dumps(summary_data, ensure_ascii=False) if summary_data else None,
                trends=trends, anomalies=anomalies,
                llm_provider=final_result.get("llm_provider", ""),
                llm_model=final_result.get("llm_model", ""),
                processing_time_ms=final_result.get("processing_time_ms", 0),
            )
            db.add(analysis_record)
            await db.commit()

            yield {"data": json.dumps({
                "progress": 100,
                "message": f"분석 완료! ({len(sampled)}/{total_count}건 샘플 분석, DB 저장됨)",
            }, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# POST /reviews/analyze — 분석 실행
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_reviews(req: AnalyzeRequest, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """리뷰 분석을 실행합니다 (수동).

    1. ChromaDB에서 리뷰 조회 (멀티테넌트 필터링)
    2. LLM으로 감성분석 + 키워드 + 요약
    3. 트렌드/이상 탐지
    4. DB에 결과 저장
    """
    # 임베딩된 리뷰가 없으면 DB에서 자동 동기화
    if _rag.get_count() == 0:
        await _rag.sync_from_db(db)

    # 멀티테넌트 필터링 (Design §4.3)
    product_ids = await _get_seller_product_ids(db, seller_id=None)
    if product_ids is not None:
        reviews = _rag.get_reviews_by_products(product_ids)
    else:
        reviews = _rag.get_all_reviews()
    if not reviews:
        raise HTTPException(404, "분석할 리뷰가 없습니다. 먼저 /embed를 실행하세요.")

    total_count = len(reviews)

    # 층화 샘플링으로 대표 리뷰 추출
    sampled = _stratified_sample(reviews, req.sample_size)

    # 분석용 데이터 준비
    analysis_reviews = [
        {
            "id": r["id"],
            "text": r["text"],
            "rating": r["metadata"].get("rating", 0),
            "platform": r["metadata"].get("platform", ""),
            "date": r["metadata"].get("date", ""),
        }
        for r in sampled
    ]

    # LLM 분석 실행
    result = await _analyzer.analyze_batch(analysis_reviews, batch_size=req.batch_size)

    # 트렌드/이상 탐지
    sentiments_with_date = [
        {**s, "date": next((r["date"] for r in analysis_reviews if str(r["id"]) == str(s.get("id"))), "")}
        for s in result.get("sentiments", [])
    ]
    trends = _trend_detector.calculate_weekly_trends(sentiments_with_date)
    anomalies = _trend_detector.detect_anomalies(trends)

    # DB 저장
    summary_data = result.get("summary", {})
    analysis_record = ReviewAnalysis(
        analysis_type="manual",
        target_scope=req.scope,
        review_count=total_count,
        sentiment_summary=result.get("sentiment_summary"),
        keywords=[kw if isinstance(kw, dict) else kw for kw in result.get("keywords", [])],
        summary=json.dumps(summary_data, ensure_ascii=False) if summary_data else None,
        trends=[t if isinstance(t, dict) else t for t in trends],
        anomalies=[a if isinstance(a, dict) else a for a in anomalies],
        llm_provider=result.get("llm_provider", ""),
        llm_model=result.get("llm_model", ""),
        processing_time_ms=result.get("processing_time_ms", 0),
    )
    db.add(analysis_record)
    await db.commit()
    await db.refresh(analysis_record)

    return AnalyzeResponse(
        analysis_id=analysis_record.id,
        status="completed",
        review_count=len(analysis_reviews),
        sentiment_summary=SentimentSummary(**result.get("sentiment_summary", {})),
        keywords=[KeywordItem(**kw) for kw in result.get("keywords", [])],
        summary=SummaryData(**summary_data) if isinstance(summary_data, dict) else SummaryData(),
        anomalies=[AnomalyAlert(**a) for a in anomalies],
        processing_time_ms=result.get("processing_time_ms", 0),
        llm_provider=result.get("llm_provider", ""),
        llm_model=result.get("llm_model", ""),
    )


# ---------------------------------------------------------------------------
# GET /reviews/analysis — 분석 결과 조회
# ---------------------------------------------------------------------------

@router.get("/analysis")
async def get_latest_analysis(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """최신 분석 결과를 조회합니다."""
    stmt = select(ReviewAnalysis).order_by(desc(ReviewAnalysis.created_at)).limit(1)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(404, "분석 결과가 없습니다. 먼저 /analyze를 실행하세요.")

    summary_data = {}
    if record.summary:
        try:
            summary_data = json.loads(record.summary) if isinstance(record.summary, str) else record.summary
        except (json.JSONDecodeError, TypeError):
            summary_data = {}

    return {
        "analysis_id": record.id,
        "analysis_type": record.analysis_type,
        "target_scope": record.target_scope,
        "review_count": record.review_count,
        "sentiment_summary": record.sentiment_summary or {},
        "keywords": record.keywords or [],
        "summary": summary_data,
        "trends": record.trends or [],
        "anomalies": record.anomalies or [],
        "processing_time_ms": record.processing_time_ms,
        "llm_provider": record.llm_provider,
        "llm_model": record.llm_model,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


# ---------------------------------------------------------------------------
# POST /reviews/search — RAG 의미 검색
# ---------------------------------------------------------------------------

@router.post("/search", response_model=SearchResponse)
async def search_reviews(
    req: SearchRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """자연어 질의로 유사 리뷰를 검색합니다 (RAG).

    멀티테넌트: seller_id가 있으면 해당 판매자의 상품 리뷰만 검색합니다.
    """
    # 컬렉션 이름 변경(예: reviews_bge_m3 → reviews_voyage_v35) 후 최초 요청 시
    # 새 컬렉션이 비어 있으므로 여기서 전체 재임베딩을 수행하는 것이
    # 현재의 "empty-new-collection window" 완화 장치이다.
    # 주의: 재임베딩은 수 분이 걸릴 수 있어 첫 요청이 지연된다.
    # 운영 시에는 트래픽 컷오버 전에 docs/runbooks/review-embedding-migration.md
    # 절차대로 수동 sync_from_db 를 선행하여 사용자 대기를 피한다.
    if _rag.get_count() == 0:
        await _rag.sync_from_db(db)

    filters = None
    if req.filters:
        filters = req.filters.model_dump(exclude_none=True)

    # 멀티테넌트 필터링 (Design §4.3)
    product_ids = await _get_seller_product_ids(db, seller_id=None)
    if product_ids is not None:
        filters = filters or {}
        filters["product_id"] = {"$in": product_ids}

    results = _rag.search(query=req.query, top_k=req.top_k, filters=filters)

    return SearchResponse(
        results=[SearchResult(**r) for r in results],
        total=len(results),
    )


# ---------------------------------------------------------------------------
# GET /reviews/trends — 트렌드 데이터
# ---------------------------------------------------------------------------

@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    period: str = Query("weekly", description="weekly 또는 monthly"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """트렌드/이상 탐지 데이터를 반환합니다."""
    stmt = select(ReviewAnalysis).order_by(desc(ReviewAnalysis.created_at)).limit(1)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record or not record.trends:
        # DB에 분석 결과가 없으면 빈 응답 반환
        return TrendsResponse(trends=[], anomalies=[])

    return TrendsResponse(
        trends=[TrendData(**t) for t in (record.trends or [])],
        anomalies=[AnomalyAlert(**a) for a in (record.anomalies or [])],
    )


# ---------------------------------------------------------------------------
# GET /reviews/report/pdf — PDF 리포트 다운로드
# ---------------------------------------------------------------------------

@router.get("/report/pdf")
async def download_report(
    analysis_id: int | None = Query(None, description="특정 분석 ID (미지정 시 최신)"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """분석 결과를 PDF 리포트로 다운로드합니다."""
    if analysis_id:
        stmt = select(ReviewAnalysis).where(ReviewAnalysis.id == analysis_id)
    else:
        stmt = select(ReviewAnalysis).order_by(desc(ReviewAnalysis.created_at)).limit(1)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(404, "분석 결과가 없습니다. 먼저 /analyze를 실행하세요.")

    summary_data = {}
    if record.summary:
        try:
            summary_data = json.loads(record.summary) if isinstance(record.summary, str) else record.summary
        except (json.JSONDecodeError, TypeError):
            summary_data = {}

    analysis_data = {
        "sentiment_summary": record.sentiment_summary or {},
        "keywords": record.keywords or [],
        "summary": summary_data,
        "anomalies": record.anomalies or [],
        "processing_time_ms": record.processing_time_ms or 0,
        "llm_provider": record.llm_provider or "",
        "llm_model": record.llm_model or "",
    }

    pdf_bytes = _report_generator.generate_pdf(analysis_data)

    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=review-analysis-report.pdf"},
    )


# ---------------------------------------------------------------------------
# GET/PUT /reviews/settings — 자동 분석 설정
# ---------------------------------------------------------------------------

@router.get("/settings", response_model=AnalysisSettings)
async def get_settings(_user: User = Depends(get_current_user)):
    """자동 분석 설정을 조회합니다."""
    return _settings


@router.put("/settings", response_model=AnalysisSettings)
async def update_settings(req: AnalysisSettingsUpdate, _user: User = Depends(get_current_user)):
    """자동 분석 설정을 변경합니다."""
    global _settings

    update_data = req.model_dump(exclude_none=True)
    current = _settings.model_dump()
    current.update(update_data)
    _settings = AnalysisSettings(**current)

    return _settings
