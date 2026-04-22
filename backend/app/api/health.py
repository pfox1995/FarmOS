import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """서버 상태."""
    try:
        await db.execute(select(1))
        db_ok = True
    except Exception as exc:
        logger.exception("health_check.db_failed err=%s", exc)
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "storage": "postgres",
    }
