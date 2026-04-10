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

    # IoT 디바이스 API Key (ESP8266 인증용)
    IOT_API_KEY: str = "farmos-iot-default-key"

    # KMA (기상청 API)
    KMA_ENCODING_KEY: str = ""
    KMA_DECODING_KEY: str = ""

    # KAMIS (농산물유통정보 API)
    KAMIS_API_KEY: str = ""
    KAMIS_CERT_ID: str = ""

    # Sensor thresholds
    SOIL_MOISTURE_LOW: float = 55.0
    SOIL_MOISTURE_HIGH: float = 70.0

    # OpenRouter (LLM API)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "google/gemma-4-31b-it"

    # Groq (Whisper STT)
    GROQ_API_KEY: str = ""
    GROQ_STT_URL: str = "https://api.groq.com/openai/v1/audio/transcriptions"
    GROQ_STT_MODEL: str = "whisper-large-v3"

    # 식품안전나라 Open API (농약 DB)
    FOOD_SAFETY_API_KEY: str = ""

    # LLM Provider (리뷰 분석용)
    LLM_PROVIDER: str = "ollama"  # ollama | openrouter | ollama_remote
    LLM_MODEL: str = "llama3.1:8b"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_REMOTE_URL: str = ""  # RunPod 등 원격 Ollama URL

    # Review Analysis
    REVIEW_ANALYSIS_BATCH_SIZE: int = 20
    REVIEW_ANALYSIS_MAX_RETRIES: int = 2

    # AI Agent (IoT 자동 제어)
    AI_AGENT_MODEL: str = "openai/gpt-5-nano"
    AI_AGENT_LLM_INTERVAL: int = 300  # LLM 호출 최소 간격 (초)
    AI_AGENT_RULE_INTERVAL: int = 30  # 규칙 판단 간격 (초)

    # 농장 위치 (기상청 격자좌표)
    FARM_NX: int = 84   # 경북 상주 기준
    FARM_NY: int = 106

    # 한글 폰트 (PDF 생성용)
    FONT_PATH: str = "C:/Windows/Fonts/malgun.ttf"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
