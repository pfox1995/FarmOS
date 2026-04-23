"""애플리케이션 설정 — 환경변수를 한 곳에서 관리합니다."""
import re

from pydantic_settings import BaseSettings

from app.paths import BACKEND_ROOT


class Settings(BaseSettings):
    # ── 데이터베이스 ────────────────────────────────────────────────────────
    # PostgreSQL 연결 주소 (driver://user:pass@host:port/dbname)
    database_url: str = ""

    # ── 보안 및 인증 ────────────────────────────────────────────────────────
    # JWT 시크릿 키 (FarmOS 백엔드와 반드시 동일해야 함 — 공유 인증)
    jwt_secret_key: str = ""
    
    # CORS 허용 도메인 (JSON 배열 형식으로 작성하거나 * 사용 가능)
    allow_origins: list[str] = []

    # ── 외부 API 연동 ───────────────────────────────────────────────────────
    # FarmOS 백엔드 연동 주소 (공유 인증 및 데이터 조회용)
    farmos_api_url: str = ""
    
    # 공공데이터포털 - 한국천문연구원 특일 정보제공 서비스 키
    anniversary_api_key: str = ""

    # ── 임베딩 (RAG) ────────────────────────────────────────────────────────
    # 시딩(seed_rag.py)과 서버 실행 시 반드시 동일한 provider + model을 사용하세요.
    # provider: openrouter | ollama | sentence_transformers | openai
    # ⚠️  변경 시 re-seed 필요.
    embed_provider: str = ""
    
    # openrouter 기본값: openai/text-embedding-3-small (PRIMARY_LLM_API_KEY 재사용)
    # sentence_transformers 기본값: jhgan/ko-sroberta-multitask (한국어 특화)
    # openai 기본값: text-embedding-3-small
    # 비워두면 provider별 기본값 사용
    embed_model: str = ""
    embed_api_key: str = ""      # openai provider 전용 (openrouter는 primary_llm_api_key 재사용)
    embed_base_url: str = ""     # openai-compatible 엔드포인트 오버라이드 (선택)

    # Ollama 사용 시 설정 (embed_provider=ollama 일 때 사용)
    ollama_base_url: str = ""
    ollama_embed_model: str = ""

    # ── LLM 서비스 ──────────────────────────────────────────────────────────
    # Utility LLM (리포트 생성 및 비용 분류 전용 — OpenAI 호환, Ollama·OpenRouter 모두 가능)
    utility_llm_base_url: str = ""
    utility_llm_api_key: str = ""
    utility_llm_model: str = ""

    # Primary LLM (챗봇 에이전트 루프 전용 — OpenRouter / Ollama / OpenAI 등)
    primary_llm_base_url: str = ""
    primary_llm_api_key: str = ""
    primary_llm_model: str = ""

    # Fallback LLM (Anthropic Claude) — 없으면 폴백 비활성화
    anthropic_api_key: str = ""
    claude_fallback_model: str = ""

    # ── 에이전트 설정 ───────────────────────────────────────────────────────
    # 에이전트 최대 반복 횟수
    agent_max_iterations: int = 10
    
    # true → SupervisorExecutor (멀티 에이전트 + LangGraph OrderGraph)
    # false → 기존 단일 AgentExecutor
    use_multi_agent: bool = False

    # ── 기타 설정 ────────────────────────────────────────────────────────────
    # 정책 문서 폴더 경로 (PDF/DOCX). 기본값: shopping_mall/backend/ai/docs/
    # 다른 위치를 쓰려면 .env에 POLICY_DOCS_DIR=/절대/경로 로 지정.
    policy_docs_dir: str = str(BACKEND_ROOT / "ai" / "docs")

    @property
    def langgraph_postgres_url(self) -> str:
        """AsyncPostgresSaver(psycopg3)용 URL — SQLAlchemy 드라이버 접미사 제거.

        예: postgresql+asyncpg://... → postgresql://...
        PostgreSQL URL이 아닌 경우 ValueError를 발생시킵니다.
        """
        url = self.database_url
        if not re.match(r"^postgres(?:ql)?(?:\+\w+)?://", url):
            scheme_match = re.match(r"^([^:/]+)", url)
            detected = scheme_match.group(1) if scheme_match else "(unknown)"
            raise ValueError(
                f"DATABASE_URL이 PostgreSQL URL이 아닙니다 (감지된 스킴: {detected!r}). "
                "AsyncPostgresSaver는 PostgreSQL 전용입니다."
            )
        return re.sub(r"^(postgres(?:ql)?)\+\w+://", r"\1://", url)

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
