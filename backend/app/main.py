import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.services.ai_agent_bridge import AiAgentBridge

from app.api import (
    ai_agent,
    auth,
    health,
    journal,
    knowledge,
    market,
    pesticide,
    review_analysis,
    diagnosis,
)
from app.core.config import settings
from app.core.database import async_session, close_db, init_db
from app.core.security import hash_password
from app.models.user import User  # noqa: F401 — Base.metadata 등록용
from app.models.review_analysis import ReviewAnalysis, ReviewSentiment  # noqa: F401
from app.models.diagnosis import DiagnosisHistory  # noqa: F401
from app.models.journal import JournalEntry  # noqa: F401
from app.models.ai_agent import (  # noqa: F401 — Base.metadata 등록용 (agent-action-history)
    AiAgentDecision,
    AiAgentActivityDaily,
    AiAgentActivityHourly,
)


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

    # AI Agent Bridge (agent-action-history) — Relay patch 적용 시 활성화
    bridge: AiAgentBridge | None = None
    if settings.AI_AGENT_BRIDGE_ENABLED:
        try:
            bridge = AiAgentBridge(settings=settings, session_factory=async_session)
            await bridge.start()
            app.state.ai_agent_bridge = bridge
        except Exception as exc:  # noqa: BLE001 — Bridge 실패가 BE 기동 막지 않음
            logging.getLogger(__name__).warning(
                "ai_agent_bridge.start_failed err=%s", exc
            )

    yield

    if bridge is not None:
        try:
            await bridge.stop()
        except Exception:  # noqa: BLE001
            pass
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
app.include_router(journal.router, prefix=settings.API_V1_PREFIX)
app.include_router(knowledge.router, prefix=settings.API_V1_PREFIX)
app.include_router(pesticide.router, prefix=settings.API_V1_PREFIX)
app.include_router(market.router, prefix=settings.API_V1_PREFIX)
app.include_router(review_analysis.router, prefix=settings.API_V1_PREFIX)
app.include_router(diagnosis.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai_agent.router, prefix=settings.API_V1_PREFIX)
