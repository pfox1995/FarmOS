"""농약 DB 동기화 — 식품안전나라 Open API (I1910) 전체 데이터를 로컬 DB에 캐싱."""

import asyncio

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.pesticide import PesticideProduct

API_BASE = "http://openapi.foodsafetykorea.go.kr/api"
SERVICE_ID = "I1910"
PAGE_SIZE = 500
REQUEST_DELAY = 0.3
MAX_RETRIES = 1
REQUEST_TIMEOUT = 5.0


async def _fetch_page(
    client: httpx.AsyncClient, start: int, end: int
) -> tuple[list[dict], int]:
    """API 1페이지 호출 (재시도 포함). (rows, total_count) 반환."""
    url = f"{API_BASE}/{settings.FOOD_SAFETY_API_KEY}/{SERVICE_ID}/json/{start}/{end}"

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = await client.get(url)
            resp.raise_for_status()

            raw = resp.text
            if raw.strip().startswith("<"):
                raise ValueError("HTML response")

            data = resp.json()
            svc = data.get(SERVICE_ID, {})

            result = svc.get("RESULT", {})
            if result and result.get("CODE") != "INFO-000":
                raise ValueError(f"API error: {result.get('MSG', 'unknown')}")

            total_str = svc.get("total_count", "0")
            total = int(total_str) if total_str else 0
            rows = svc.get("row", [])
            return rows, total
        except Exception:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(0.5)
                continue
            raise


def _extract_row(row: dict) -> dict:
    """API row에서 전체 필드 추출."""
    return {
        "product_name": (row.get("PRDLST_KOR_NM") or "").strip(),
        "brand_name": (row.get("BRND_NM") or "").strip() or None,
        "company": (row.get("CPR_NM") or "").strip() or None,
        "purpose": (row.get("PRPOS_DVS_CD_NM") or "").strip() or None,
        "form_type": (row.get("MDC_SHAP_NM") or "").strip() or None,
        "crop_name": (row.get("CROPS_NM") or "").strip() or None,
        "disease_name": (row.get("SICKNS_HLSCT_NM_WEEDS_NM") or "").strip() or None,
        "dilution": (row.get("DILU_DRNG") or "").strip() or None,
        "usage_method": (row.get("AGCHM_USE_MTHD") or "").strip() or None,
        "usage_period": (row.get("USE_PPRTM") or "").strip() or None,
        "usage_count": (row.get("USE_TMNO") or "").strip() or None,
        "toxicity": (row.get("PERSN_LVSTCK_TOXCTY") or "").strip() or None,
    }


async def sync_pesticides(db: AsyncSession) -> int:
    """증분 동기화: DB에 저장된 건수부터 이어서 가져오기.

    - DB가 비어있으면 처음부터 전체 동기화
    - 일부만 있으면 이어서 나머지 저장
    - 이미 전체가 있으면 스킵
    """
    existing = await get_pesticide_count(db)

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        # 첫 페이지로 total 확인
        rows, total = await _fetch_page(client, 1, min(PAGE_SIZE, 1))
        total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

        if existing >= total:
            print(f"[Pesticide Sync] 이미 최신 상태 ({existing}/{total}건)")
            return existing

        # 이어서 가져올 시작 위치
        start_from = existing + 1
        start_page = (start_from - 1) // PAGE_SIZE + 1
        print(
            f"[Pesticide Sync] {existing}/{total}건 저장됨, {start_from}번부터 이어서 동기화..."
        )

        saved_count = 0
        failed_pages = 0

        for page_num in range(start_page, total_pages + 1):
            start = (page_num - 1) * PAGE_SIZE + 1
            end = min(page_num * PAGE_SIZE, total)
            await asyncio.sleep(REQUEST_DELAY)

            try:
                rows, _ = await _fetch_page(client, start, end)
                new_in_page = 0
                for row in rows:
                    p = _extract_row(row)
                    if p["product_name"]:
                        db.add(PesticideProduct(**p))
                        saved_count += 1
                        new_in_page += 1
                print(
                    f"[Pesticide Sync] {page_num}/{total_pages} OK (+{new_in_page}건, 누적 {existing + saved_count}건)"
                )
            except Exception as e:
                failed_pages += 1
                print(f"[Pesticide Sync] {page_num}/{total_pages} FAIL: {e}")
                continue

            if page_num % 10 == 0:
                await db.commit()

        await db.commit()

    final_count = existing + saved_count
    print(
        f"[Pesticide Sync] 동기화 완료: {final_count}/{total}건 (신규 {saved_count}, 실패 {failed_pages}페이지)"
    )
    return final_count


async def get_pesticide_count(db: AsyncSession) -> int:
    """현재 DB에 저장된 농약 레코드 수."""
    result = await db.execute(select(func.count(PesticideProduct.id)))
    return result.scalar() or 0


async def init_pesticide_cache():
    """농약 DB 증분 동기화 — 서버 시작 시 백그라운드에서 호출."""
    from app.core.database import async_session

    async with async_session() as db:
        try:
            await sync_pesticides(db)
        except Exception as e:
            print(f"[Warning] 농약 DB 동기화 실패: {e}")
