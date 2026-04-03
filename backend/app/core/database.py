"""SQLAlchemy async engine & session 관리."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI Depends용 DB 세션 제공."""
    async with async_session() as session:
        yield session


async def init_db():
    """앱 시작 시 테이블 생성."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
