from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "FarmOS Backend"
    API_V1_PREFIX: str = "/api/v1"

    # Database (PostgreSQL)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/farmos"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://iot.lilpa.moe"
    ]

    # ChromaDB (벡터 데이터베이스)
    CHROMA_DB_PATH: str = "./chroma_data"

    # JWT
    JWT_SECRET_KEY: str = ""

    # KMA (기상청 API)
    KMA_ENCODING_KEY: str = ""
    KMA_DECODING_KEY: str = ""

    # KAMIS (농산물유통정보 API)
    KAMIS_API_KEY: str = ""
    KAMIS_CERT_ID: str = ""

    # OpenRouter (LLM API) — 진단/일지/공통 LLM 클라이언트에서 사용
    # NOTE: LiteLLM 프록시에 등록된 모델명을 그대로 사용해야 함 (접두사 없이)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_URL: str = "https://litellm.lilpa.moe/v1"
    OPENROUTER_MODEL: str = "gpt-5-nano"
    OPENROUTER_PEST_RAG_MODEL: str = "gpt-5-nano"

    # LiteLLM 프록시 — 리뷰 자동화(임베딩) 전용 네이밍 (실제 호스트는 OPENROUTER_URL 과 동일 가능)
    LITELLM_API_KEY: str = ""
    LITELLM_URL: str = "https://litellm.lilpa.moe/v1"
    LITELLM_MODEL: str = "gpt-5-nano"

    # 외부 데이터 API (기상청, NCPMS, 농약안전정보시스템)
    WEATHER_API_KEY: str = ""
    NCPMS_API_KEY: str = ""
    PESTICIDE_API_KEY: str = ""

    # Groq (Whisper STT)
    GROQ_API_KEY: str = ""
    GROQ_STT_URL: str = "https://api.groq.com/openai/v1/audio/transcriptions"
    GROQ_STT_MODEL: str = "whisper-large-v3"

    # 식품안전나라 Open API (농약 DB)
    FOOD_SAFETY_API_KEY: str = ""

    # LLM Provider (리뷰 분석용)
    LLM_PROVIDER: str = "openrouter"  # ollama | openrouter | ollama_remote
    LLM_MODEL: str = "llama3.1:8b"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_REMOTE_URL: str = ""  # RunPod 등 원격 Ollama URL

    # Review Embedding (LiteLLM 프록시 경유, VoyageAI 등)
    EMBED_MODEL: str = "voyage-3.5"
    EMBED_DIM: int = 1024

    # LLM 리즈닝 강도 (GPT-5 계열 reasoning 모델용)
    # minimal | low | medium | high  또는 "none"(파라미터 미전송)
    # non-reasoning 모델(gemma, gpt-oss 등)은 무시됨
    LLM_REASONING_EFFORT: str = "minimal"

    # Review Analysis
    REVIEW_ANALYSIS_BATCH_SIZE: int = 40
    REVIEW_ANALYSIS_MAX_RETRIES: int = 2

    # 앱 타임존 (집계 일/시간 버킷의 로컬 기준)
    APP_TIMEZONE: str = "Asia/Seoul"

    # AI Agent (IoT 자동 제어)
    AI_AGENT_MODEL: str = "openai/gpt-5-mini"
    AI_AGENT_LLM_INTERVAL: int = 300  # LLM 호출 최소 간격 (초)
    AI_AGENT_RULE_INTERVAL: int = 30  # 규칙 판단 간격 (초)

    # AI Agent Action History Bridge (Relay → FarmOS 미러)
    IOT_RELAY_BASE_URL: str = "http://localhost:9000"
    # 실제 키는 반드시 .env / 환경변수(IOT_RELAY_API_KEY) 로 주입한다.
    # 빈 문자열이면 AI_AGENT_BRIDGE_ENABLED=True 라도 Bridge 는 안전하게 비활성화된다.
    IOT_RELAY_API_KEY: str = ""
    AI_AGENT_BRIDGE_ENABLED: bool = False  # Relay 패치 적용 전 기본 off
    AI_AGENT_MIRROR_TTL_DAYS: int = 30
    AI_AGENT_BACKFILL_PAGE_SIZE: int = 200

    # 농장 위치 (기상청 격자좌표)
    FARM_NX: int = 84   # 경북 상주 기준
    FARM_NY: int = 106

    # 한글 폰트 (PDF 생성용)
    FONT_PATH: str = "C:/Windows/Fonts/malgun.ttf"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
