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

from app.core.config import settings
from app.database import Base, engine
from app.routers import products, categories, cart, orders, users, reviews, stores, wishlists
from app.routers import shipments, calendar, reports, analytics, chatbot, admin
from app import models  # noqa: F401 - Import models to register them with Base

logger = logging.getLogger(__name__)

# Create tables on startup
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle: start and stop APScheduler."""
    sched = None
    try:
        from jobs.scheduler import setup_scheduler
        sched = setup_scheduler()
        sched.start()
        logger.info("APScheduler started.")
    except Exception as e:
        logger.warning(f"Failed to start scheduler: {e}")

    try:
        from app.core.config import settings
        from app.routers.chatbot import set_chatbot_service
        from ai.rag import RAGService
        from ai.agent import OpenAIAgentClient, ClaudeAgentClient, AgentExecutor
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from ai.agent.subagents.cs.tools import CS_TOOLS
        from ai.agent.subagents.cs.prompts import CS_INPUT_PROMPT, CS_OUTPUT_PROMPT
        from ai.agent.order_graph.graph import build_order_graph
        from ai.agent.supervisor import SupervisorExecutor
        from ai.agent.supervisor.prompts import SUPERVISOR_INPUT_PROMPT, SUPERVISOR_OUTPUT_PROMPT
        from app.services.multi_agent_chatbot import MultiAgentChatbotService

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

        async with AsyncPostgresSaver.from_conn_string(settings.langgraph_postgres_url) as checkpointer:
            await checkpointer.setup()
            order_graph = build_order_graph(checkpointer)

            cs_executor = AgentExecutor(
                primary=primary,
                fallback=fallback,
                rag_service=rag,
                tools=CS_TOOLS,
                max_iterations=settings.agent_max_iterations,
            )
            supervisor = SupervisorExecutor(
                primary=primary,
                fallback=fallback,
                cs_executor=cs_executor,
                cs_input_prompt=CS_INPUT_PROMPT,
                cs_output_prompt=CS_OUTPUT_PROMPT,
                order_graph=order_graph,
            )
            set_chatbot_service(MultiAgentChatbotService(
                supervisor,
                input_prompt=SUPERVISOR_INPUT_PROMPT,
                output_prompt=SUPERVISOR_OUTPUT_PROMPT,
            ))
            logger.info("Multi-agent chatbot service initialized.")
            yield

    except Exception as e:
        logger.warning(f"Failed to initialize chatbot service: {e}")
        yield

    finally:
        if sched is not None:
            sched.shutdown(wait=False)
            logger.info("APScheduler stopped.")


app = FastAPI(title="Shopping Mall API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
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
app.include_router(admin.router)


@app.get("/")
def root():
    return {"message": "Shopping Mall API is running", "docs": "/docs"}
