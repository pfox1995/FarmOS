import logging
from contextlib import asynccontextmanager
from pathlib import Path


def _setup_app_logging() -> None:
    """앱 로거(ai.*, app.*)에 UTF-8 파일 핸들러를 붙인다.

    chatbot.log에만 기록하고 stdout에는 쓰지 않는다.
    - stdout(shop-be.log): uvicorn 인프라 로그(ASCII) 전용
    - chatbot.log: 챗봇 비즈니스 로그(한글 포함) 전용, encoding="utf-8" 고정

    stdout 리다이렉트 시 Windows cp949 인코딩 문제를 완전히 회피한다.
    """
    from app.paths import LOG_DIR
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "chatbot.log"

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)

    for name in ("ai", "app", "httpx", "chromadb"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)
        if not any(isinstance(h, logging.FileHandler) for h in lg.handlers):
            lg.addHandler(file_handler)
            lg.propagate = False


# 모듈 임포트 시점에 핸들러 등록 — lifespan보다 앞서 실행되어
# 워커 프로세스 전체 생애 동안 chatbot.log에 UTF-8로 기록된다.
_setup_app_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import products, categories, cart, orders, users, reviews, stores, wishlists
from app.routers import shipments, calendar, reports, analytics, chatbot
from app import models  # noqa: F401 - Import models to register them with Base

logger = logging.getLogger(__name__)

# Create tables on startup
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle: start and stop APScheduler."""
    try:
        from jobs.scheduler import setup_scheduler
        sched = setup_scheduler()
        sched.start()
        logger.info("APScheduler started.")
    except Exception as e:
        logger.warning(f"Failed to start scheduler: {e}")
        sched = None

    try:
        from app.core.config import settings
        from app.routers.chatbot import set_chatbot_service
        from ai.rag import RAGService
        from ai.agent import OpenAIAgentClient, ClaudeAgentClient, AgentExecutor, TOOL_DEFINITIONS
        from ai.agent.prompts import AGENT_SYSTEM_PROMPT
        from app.services.agent_chatbot import AgentChatbotService

        rag = RAGService()

        primary = OpenAIAgentClient(
            base_url=settings.primary_llm_base_url,
            api_key=settings.primary_llm_api_key,
            model=settings.primary_llm_model,
        )
        fallback = ClaudeAgentClient(
            api_key=settings.anthropic_api_key,
            model=settings.claude_fallback_model,
        ) if settings.anthropic_api_key else None

        executor = AgentExecutor(
            primary=primary,
            fallback=fallback,
            rag_service=rag,
            tools=TOOL_DEFINITIONS,
            max_iterations=settings.agent_max_iterations,
        )
        set_chatbot_service(AgentChatbotService(executor, AGENT_SYSTEM_PROMPT))
        logger.info("Agent chatbot service initialized.")

    except Exception as e:
        logger.warning(f"Failed to initialize chatbot service: {e}")

    yield

    if sched is not None:
        sched.shutdown(wait=False)
        logger.info("APScheduler stopped.")


app = FastAPI(title="Shopping Mall API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing routers
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(users.router)
app.include_router(reviews.router)
app.include_router(stores.router)
app.include_router(wishlists.router)

# Backoffice routers
app.include_router(shipments.router)
app.include_router(calendar.router)
app.include_router(reports.router)
app.include_router(analytics.router)
app.include_router(chatbot.router)


@app.get("/")
def root():
    return {"message": "Shopping Mall API is running", "docs": "/docs"}
