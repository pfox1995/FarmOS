"""영농일지 CRUD 저장소."""

from datetime import date, datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal import JournalEntry
from app.schemas.journal import JournalEntryCreate, JournalEntryUpdate


async def create_entry(
    db: AsyncSession, user_id: str, data: JournalEntryCreate
) -> JournalEntry:
    entry = JournalEntry(user_id=user_id, **data.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def get_entry(
    db: AsyncSession, user_id: str, entry_id: int
) -> JournalEntry | None:
    result = await db.execute(
        select(JournalEntry).where(
            JournalEntry.id == entry_id,
            JournalEntry.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_entries(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    date_from: date | None = None,
    date_to: date | None = None,
    work_stage: str | None = None,
    crop: str | None = None,
) -> tuple[list[JournalEntry], int]:
    base = select(JournalEntry).where(JournalEntry.user_id == user_id)
    count_q = (
        select(func.count())
        .select_from(JournalEntry)
        .where(JournalEntry.user_id == user_id)
    )

    if date_from:
        base = base.where(JournalEntry.work_date >= date_from)
        count_q = count_q.where(JournalEntry.work_date >= date_from)
    if date_to:
        base = base.where(JournalEntry.work_date <= date_to)
        count_q = count_q.where(JournalEntry.work_date <= date_to)
    if work_stage:
        base = base.where(JournalEntry.work_stage == work_stage)
        count_q = count_q.where(JournalEntry.work_stage == work_stage)
    if crop:
        base = base.where(JournalEntry.crop == crop)
        count_q = count_q.where(JournalEntry.crop == crop)

    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = base.order_by(JournalEntry.work_date.desc(), JournalEntry.id.desc())
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def update_entry(
    db: AsyncSession,
    user_id: str,
    entry_id: int,
    data: JournalEntryUpdate,
) -> JournalEntry | None:
    entry = await get_entry(db, user_id, entry_id)
    if not entry:
        return None

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entry, field, value)

    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_entry(db: AsyncSession, user_id: str, entry_id: int) -> bool:
    entry = await get_entry(db, user_id, entry_id)
    if not entry:
        return False
    await db.delete(entry)
    await db.commit()
    return True


# ── 누락 항목 체크 ──


def check_missing_fields(entries: list[JournalEntry]) -> list[dict]:
    """영농일지 목록에서 누락 필드를 검사.

    Returns:
        [{"entry_id": int, "field_name": str, "message": str,
          "work_date": str, "crop": str, "created_at": str}, ...]
    """
    alerts: list[dict] = []

    for entry in entries:
        eid = entry.id
        entry_meta = {
            "work_date": entry.work_date.isoformat() if entry.work_date else None,
            "crop": entry.crop,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }

        # 작물관리인데 농약/비료 사용 정보가 없는 경우
        if entry.work_stage == "작물관리":
            if not entry.usage_pesticide_product and not entry.usage_fertilizer_product:
                alerts.append(
                    {
                        "entry_id": eid,
                        "field_name": "usage_pesticide_product / usage_fertilizer_product",
                        "message": "작물관리 작업에 농약 또는 비료 사용 정보가 없습니다.",
                        **entry_meta,
                    }
                )

        # 농약 제품명은 있는데 사용량이 없는 경우
        if entry.usage_pesticide_product and not entry.usage_pesticide_amount:
            alerts.append(
                {
                    "entry_id": eid,
                    "field_name": "usage_pesticide_amount",
                    "message": f"농약 '{entry.usage_pesticide_product}'의 사용량이 누락되었습니다.",
                    **entry_meta,
                }
            )

        # 비료 제품명은 있는데 사용량이 없는 경우
        if entry.usage_fertilizer_product and not entry.usage_fertilizer_amount:
            alerts.append(
                {
                    "entry_id": eid,
                    "field_name": "usage_fertilizer_amount",
                    "message": f"비료 '{entry.usage_fertilizer_product}'의 사용량이 누락되었습니다.",
                    **entry_meta,
                }
            )

        # 농약 구입 종류는 있는데 제품명/구입량이 없는 경우
        if entry.purchase_pesticide_type:
            if not entry.purchase_pesticide_product:
                alerts.append(
                    {
                        "entry_id": eid,
                        "field_name": "purchase_pesticide_product",
                        "message": "농약 구입 제품명이 누락되었습니다.",
                        **entry_meta,
                    }
                )
            if not entry.purchase_pesticide_amount:
                alerts.append(
                    {
                        "entry_id": eid,
                        "field_name": "purchase_pesticide_amount",
                        "message": "농약 구입량이 누락되었습니다.",
                        **entry_meta,
                    }
                )

        # 비료 구입 종류는 있는데 제품명/구입량이 없는 경우
        if entry.purchase_fertilizer_type:
            if not entry.purchase_fertilizer_product:
                alerts.append(
                    {
                        "entry_id": eid,
                        "field_name": "purchase_fertilizer_product",
                        "message": "비료 구입 제품명이 누락되었습니다.",
                        **entry_meta,
                    }
                )
            if not entry.purchase_fertilizer_amount:
                alerts.append(
                    {
                        "entry_id": eid,
                        "field_name": "purchase_fertilizer_amount",
                        "message": "비료 구입량이 누락되었습니다.",
                        **entry_meta,
                    }
                )

    return alerts


# ── 일일 요약 ──


def _generate_summary_template(
    entries: list[JournalEntry],
    target_date: date,
    crops: list[str],
    stages: list[str],
    weather: str | None,
    missing: list[dict],
) -> str:
    """템플릿 기반 요약문 (LLM 폴백용)."""
    date_str = target_date.strftime("%Y년 %m월 %d일")
    parts = [f"{date_str} 영농보고서:"]
    parts.append(f"총 {len(entries)}건의 작업을 기록했습니다.")
    if crops:
        parts.append(f"작목: {', '.join(crops)}.")
    for stage in stages:
        count = sum(1 for e in entries if e.work_stage == stage)
        parts.append(f"{stage} {count}건.")
    if weather:
        parts.append(f"날씨: {weather}.")
    if missing:
        parts.append(f"누락 항목 {len(missing)}건이 있습니다. 확인이 필요합니다.")
    return " ".join(parts)


async def _generate_summary_llm(
    entries: list[JournalEntry],
    target_date: date,
    weather: str | None,
    missing: list[dict],
) -> str | None:
    """OpenRouter LLM으로 자연스러운 요약문 생성. 실패 시 None 반환."""
    # 일지 데이터를 텍스트로 정리
    entry_lines = []
    for e in entries:
        line = f"- {e.crop} / {e.field_name} / {e.work_stage}"
        if e.usage_pesticide_product:
            line += f" / 농약: {e.usage_pesticide_product}"
            if e.usage_pesticide_amount:
                line += f" {e.usage_pesticide_amount}"
        if e.usage_fertilizer_product:
            line += f" / 비료: {e.usage_fertilizer_product}"
            if e.usage_fertilizer_amount:
                line += f" {e.usage_fertilizer_amount}"
        if e.detail:
            line += f" / {e.detail}"
        entry_lines.append(line)

    date_str = target_date.strftime("%Y년 %m월 %d일")
    prompt = f"""다음은 {date_str}의 영농일지 기록입니다.

{chr(10).join(entry_lines)}

날씨: {weather or "기록 없음"}
누락 항목: {len(missing)}건

위 내용을 바탕으로 '오늘의 영농보고서'를 3~5문장의 자연스러운 한국어로 작성하세요.
농부가 하루를 마치고 읽기 좋은 보고서 형식으로, 핵심 작업 내용과 주의사항을 포함하세요.
마크다운이나 제목 없이 본문만 작성하세요."""

    try:
        import httpx
        from app.core.config import settings

        url = f"{settings.OPENROUTER_URL}/chat/completions"
        headers = {"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}
        payload = {
            "model": settings.OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 영농 보고서를 작성하는 전문가입니다. 간결하고 실용적인 한국어로 보고서를 작성합니다.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip() if content else None
    except Exception:
        return None


async def get_daily_summary(db: AsyncSession, user_id: str, target_date: date) -> dict:
    """특정 날짜의 영농일지를 집계하여 요약 생성."""
    result = await db.execute(
        select(JournalEntry).where(
            JournalEntry.user_id == user_id,
            JournalEntry.work_date == target_date,
        )
    )
    entries = list(result.scalars().all())

    if not entries:
        return {
            "date": target_date.isoformat(),
            "entry_count": 0,
            "stages_worked": [],
            "crops": [],
            "weather": None,
            "missing_fields": [],
            "summary_text": f"{target_date.isoformat()} 기록된 영농일지가 없습니다.",
        }

    # 집계
    stages = list({e.work_stage for e in entries})
    crops = list({e.crop for e in entries})
    weathers = [e.weather for e in entries if e.weather]
    weather = weathers[0] if weathers else None
    missing = check_missing_fields(entries)

    # 요약문 생성 (LLM → 실패 시 템플릿 폴백)
    summary_text = await _generate_summary_llm(entries, target_date, weather, missing)
    if not summary_text:
        summary_text = _generate_summary_template(
            entries, target_date, crops, stages, weather, missing
        )

    return {
        "date": target_date.isoformat(),
        "entry_count": len(entries),
        "stages_worked": stages,
        "crops": crops,
        "weather": weather,
        "missing_fields": missing,
        "summary_text": summary_text,
    }
