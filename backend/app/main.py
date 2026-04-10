from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import (
    ai_agent,
    auth,
    health,
    irrigation,
    journal,
    knowledge,
    market,
    pesticide,
    review_analysis,
    sensors,
)
from app.core.config import settings
from app.core.database import async_session, close_db, init_db
from app.core.security import hash_password
from app.models.user import User  # noqa: F401 — Base.metadata 등록용
from app.models.review_analysis import ReviewAnalysis, ReviewSentiment  # noqa: F401


async def seed_users():
    """테스트 계정이 없으면 시딩."""
    seed_data = [
        {
            "id": "farmer01",
            "name": "김사과",
            "email": "farmer01@farmos.kr",
            "password": "farm1234",
            "location": "경북 영주시",
            "area": 33.0,
            "farmname": "김사과 사과농장",
            "profile": "",
        },
        {
            "id": "parkpear",
            "name": "박배나무",
            "email": "parkpear@farmos.kr",
            "password": "pear5678",
            "location": "충남 천안시",
            "area": 25.5,
            "farmname": "박씨네 배 과수원",
            "profile": "",
        },
    ]
    async with async_session() as db:
        for data in seed_data:
            exists = await db.execute(select(User).where(User.id == data["id"]))
            if exists.scalar_one_or_none():
                continue
            user = User(
                id=data["id"],
                name=data["name"],
                email=data["email"],
                password=hash_password(data["password"]),
                location=data["location"],
                area=data["area"],
                farmname=data["farmname"],
                profile=data["profile"],
            )
            db.add(user)
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_users()
    yield
    await close_db()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(sensors.router, prefix=settings.API_V1_PREFIX)
app.include_router(irrigation.router, prefix=settings.API_V1_PREFIX)
app.include_router(journal.router, prefix=settings.API_V1_PREFIX)
app.include_router(knowledge.router, prefix=settings.API_V1_PREFIX)
app.include_router(pesticide.router, prefix=settings.API_V1_PREFIX)
app.include_router(market.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai_agent.router, prefix=settings.API_V1_PREFIX)
app.include_router(review_analysis.router, prefix=settings.API_V1_PREFIX)
