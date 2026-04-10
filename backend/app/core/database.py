"""SQLAlchemy async engine & session 관리."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI Depends용 DB 세션 제공."""
    async with async_session() as session:
        yield session


async def _ensure_column_widths():
    """기존 DB에서 컬럼 크기가 모델과 맞지 않을 때 자동 보정."""
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = 'location'"
        ))
        row = result.first()
        if row and row[0] is not None and row[0] < 100:
            await conn.execute(text(
                "ALTER TABLE users ALTER COLUMN location TYPE VARCHAR(100)"
            ))


async def _ensure_onboarding_columns():
    """온보딩 확장 필드가 없으면 추가."""
    new_columns = [
        ("main_crop", "VARCHAR(40) DEFAULT ''"),
        ("crop_variety", "VARCHAR(40) DEFAULT ''"),
        ("farmland_type", "VARCHAR(20) DEFAULT ''"),
        ("is_promotion_area", "BOOLEAN DEFAULT FALSE"),
        ("has_farm_registration", "BOOLEAN DEFAULT FALSE"),
        ("farmer_type", "VARCHAR(20) DEFAULT '일반'"),
        ("years_rural_residence", "INTEGER DEFAULT 0"),
        ("years_farming", "INTEGER DEFAULT 0"),
        ("onboarding_completed", "BOOLEAN DEFAULT FALSE"),
    ]
    async with engine.begin() as conn:
        for col_name, col_def in new_columns:
            result = await conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = :col"
            ), {"col": col_name})
            if result.first() is None:
                await conn.execute(text(
                    f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"
                ))


async def init_db():
    """앱 시작 시 테이블 생성."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_column_widths()
    await _ensure_onboarding_columns()


async def close_db():
    """앱 종료 시 커넥션 풀 정리."""
    await engine.dispose()
