"""농약 DB API 라우터 — 검색 및 동기화."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, or_, select
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
    result = await db.execute(
        select(
            distinct(PesticideProduct.ingredient_or_formulation_name),
            PesticideProduct.brand_name,
            PesticideProduct.corporation_name,
            PesticideProduct.usage_purpose_name,
            PesticideProduct.formulation_name,
        )
        .where(
            or_(
                PesticideProduct.ingredient_or_formulation_name.ilike(f"%{q}%"),
                PesticideProduct.brand_name.ilike(f"%{q}%"),
            )
        )
        .limit(limit)
    )
    products = result.all()
    return {
        # TODO: 응답 키를 모델/DB 컬럼명 기준으로 정렬 필요.
        # NOTE: backend 응답 스키마와 frontend 타입/사용처를 함께 수정해야 함.
        "results": [
            {
                "product_name": product_name,
                "brand_name": brand_name,
                "company": company,
                "purpose": purpose,
                "form_type": form_type,
            }
            for product_name, brand_name, company, purpose, form_type in products
        ],
        "total": len(products),
    }


@router.post("/sync")
async def trigger_sync(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """레거시 호환: bootstrap 적재 결과 기준으로 현재 제품 수를 반환."""
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
