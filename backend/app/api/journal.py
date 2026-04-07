"""영농일지 API 라우터."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core import journal_store
from app.core.journal_parser import parse_stt_text
from app.models.user import User
from app.schemas.journal import (
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalEntryResponse,
    JournalEntryListResponse,
    STTParseRequest,
    STTParseResponse,
    DailySummaryResponse,
)

router = APIRouter(prefix="/journal", tags=["journal"])


@router.post("/parse-stt", response_model=STTParseResponse)
async def parse_stt(
    body: STTParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """STT 텍스트를 농업ON 구조화 데이터로 파싱 + 농약 DB 매칭."""
    try:
        result = await parse_stt_text(body.raw_text)
    except Exception as e:
        raise HTTPException(502, f"LLM 연결 실패: {e}")
    # 농약 DB 매칭 후처리
    try:
        from app.core.pesticide_matcher import enrich_with_pesticide_match

        result = await enrich_with_pesticide_match(db, result)
    except Exception:
        pass  # 매칭 실패해도 파싱 결과는 정상 반환
    return result


@router.get("/daily-summary", response_model=DailySummaryResponse)
async def daily_summary(
    target_date: date = Query(..., alias="date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 날짜의 영농 요약 조회."""
    result = await journal_store.get_daily_summary(db, current_user.id, target_date)
    return result


@router.get("/missing-fields")
async def missing_fields(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """기간 내 영농일지 누락 항목 조회."""
    entries, _ = await journal_store.list_entries(
        db,
        current_user.id,
        page=1,
        page_size=1000,
        date_from=date_from,
        date_to=date_to,
    )
    alerts = journal_store.check_missing_fields(entries)
    return {"missing_fields": alerts, "total": len(alerts)}


@router.get("/export-pdf")
async def export_pdf(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """영농일지 PDF 내보내기."""
    from fastapi.responses import Response
    from app.core.journal_pdf import generate_journal_pdf

    entries, _ = await journal_store.list_entries(
        db,
        current_user.id,
        page=1,
        page_size=1000,
        date_from=date_from,
        date_to=date_to,
    )
    pdf_bytes = generate_journal_pdf(
        entries,
        farm_name=current_user.farmname or current_user.name,
        date_from=date_from,
        date_to=date_to,
    )
    filename = f"journal_{date_from}_{date_to}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=JournalEntryResponse, status_code=201)
async def create_journal_entry(
    body: JournalEntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """영농일지 생성."""
    entry = await journal_store.create_entry(db, current_user.id, body)
    return entry


@router.get("", response_model=JournalEntryListResponse)
async def list_journal_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    date_from: date | None = None,
    date_to: date | None = None,
    work_stage: str | None = None,
    crop: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """영농일지 목록 조회 (필터 + 페이징)."""
    items, total = await journal_store.list_entries(
        db, current_user.id, page, page_size, date_from, date_to, work_stage, crop
    )
    return JournalEntryListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """영농일지 단건 조회."""
    entry = await journal_store.get_entry(db, current_user.id, entry_id)
    if not entry:
        raise HTTPException(404, "영농일지를 찾을 수 없습니다.")
    return entry


@router.patch("/{entry_id}", response_model=JournalEntryResponse)
async def update_journal_entry(
    entry_id: int,
    body: JournalEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """영농일지 수정 (보낸 필드만 업데이트)."""
    entry = await journal_store.update_entry(db, current_user.id, entry_id, body)
    if not entry:
        raise HTTPException(404, "영농일지를 찾을 수 없습니다.")
    return entry


@router.delete("/{entry_id}")
async def delete_journal_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """영농일지 삭제."""
    deleted = await journal_store.delete_entry(db, current_user.id, entry_id)
    if not deleted:
        raise HTTPException(404, "영농일지를 찾을 수 없습니다.")
    return {"message": "영농일지가 삭제되었습니다."}
