"""농약 DB API 라우터 — 검색 및 동기화."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.pesticide_sync import get_pesticide_count, sync_pesticides
from app.models.pesticide import PesticideProduct
from app.models.user import User

router = APIRouter(prefix="/pesticide", tags=["pesticide"])


@router.get("/search")
async def search_pesticide(
    q: str = Query(..., min_length=1, description="검색어"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """농약 제품명/브랜드명 검색 (자동완성용)."""
    from sqlalchemy import or_

    result = await db.execute(
        select(PesticideProduct)
        .where(
            or_(
                PesticideProduct.product_name.ilike(f"%{q}%"),
                PesticideProduct.brand_name.ilike(f"%{q}%"),
            )
        )
        .limit(limit)
    )
    products = result.scalars().all()
    return {
        "results": [
            {
                "product_name": p.product_name,
                "brand_name": p.brand_name,
                "company": p.company,
                "purpose": p.purpose,
                "form_type": p.form_type,
            }
            for p in products
        ],
        "total": len(products),
    }


@router.post("/sync")
async def trigger_sync(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """농약 DB 수동 동기화 (식품안전나라 API)."""
    try:
        count = await sync_pesticides(db)
        return {"status": "ok", "synced_count": count}
    except Exception as e:
        raise HTTPException(500, f"동기화 실패: {e}")


@router.get("/count")
async def pesticide_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 DB에 캐싱된 농약 제품 수."""
    count = await get_pesticide_count(db)
    return {"count": count}
