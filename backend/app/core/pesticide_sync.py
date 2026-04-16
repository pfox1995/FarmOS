"""농약 데이터 상태 조회 유틸.

농약 원천 적재는 `bootstrap/pesticide.py`가 담당한다.
런타임에서는 `rag_pesticide_documents`를 기준으로 조회만 수행한다.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pesticide import PesticideProduct

async def sync_pesticides(db: AsyncSession) -> int:
    """레거시 호환용 엔트리포인트.

    실제 적재는 bootstrap에서 수행되므로 런타임에서는 현재 제품 수만 반환한다.
    """
    return await get_pesticide_count(db)


async def get_pesticide_count(db: AsyncSession) -> int:
    """현재 DB에 저장된 고유 제품명 개수."""
    result = await db.execute(
        select(func.count(func.distinct(PesticideProduct.ingredient_or_formulation_name)))
    )
    return result.scalar() or 0


async def init_pesticide_cache():
    """앱 시작 시 농약 문서 접근 가능 여부를 점검한다."""
    from app.core.database import async_session

    async with async_session() as db:
        try:
            await sync_pesticides(db)
        except Exception as e:
            print(f"[Warning] 농약 DB 동기화 실패: {e}")
