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


async def _ensure_ai_agent_indexes():
    """ai_agent_decisions 복합 인덱스 보장 (기존 DB 환경 대상).

    Base.metadata.create_all 은 이미 존재하는 테이블에는 인덱스를 추가하지 않으므로
    list_decisions(control_type+source 필터 + timestamp DESC 정렬) 가속용 복합 인덱스를
    idempotent 하게 생성한다. 신규 환경에서는 ORM __table_args__ 가 동일 인덱스를 만든다.
    """
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS "
            "ix_ai_agent_decisions_control_source_timestamp "
            "ON ai_agent_decisions (control_type, source, timestamp DESC)"
        ))


async def _ensure_ai_agent_activity_daily_columns():
    """ai_agent_activity_daily 의 duration_count / duration_sum 컬럼 보장.

    기존 avg_duration_ms 가 (count 전체) 기반으로 산출되어 null-duration 행으로 편향되던
    문제를 해결하기 위해 분리된 누적 카운터/합 컬럼을 추가한다. 기존 행은 0 으로 초기화되며
    이후 들어오는 decisions 부터 정확한 평균이 누적된다 (과거 데이터 backfill 은 별도 운영 작업).
    """
    new_columns = [
        ("duration_count", "INTEGER NOT NULL DEFAULT 0"),
        ("duration_sum", "BIGINT NOT NULL DEFAULT 0"),
    ]
    async with engine.begin() as conn:
        for col_name, col_def in new_columns:
            result = await conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'ai_agent_activity_daily' AND column_name = :col"
            ), {"col": col_name})
            if result.first() is None:
                await conn.execute(text(
                    f"ALTER TABLE ai_agent_activity_daily ADD COLUMN {col_name} {col_def}"
                ))


async def init_db():
    """앱 시작 시 테이블 생성."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_column_widths()
    await _ensure_onboarding_columns()
    await _ensure_ai_agent_indexes()
    await _ensure_ai_agent_activity_daily_columns()


async def close_db():
    """앱 종료 시 커넥션 풀 정리."""
    await engine.dispose()
