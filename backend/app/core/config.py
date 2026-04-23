from pathlib import Path

from pydantic_settings import BaseSettings


# 프로젝트 번들 폰트 경로 — cross-platform 기본값.
# `.env` 의 FONT_PATH / FONT_BOLD_PATH 로 개별 오버라이드 가능.
_BUNDLED_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


class Settings(BaseSettings):
    # ── 기본 설정 ──────────────────────────────────────────────────────────
    PROJECT_NAME: str = ""
    API_V1_PREFIX: str = ""
    APP_TIMEZONE: str = ""

    # ── 데이터베이스 ────────────────────────────────────────────────────────
    # 데이터베이스 (PostgreSQL)
    DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # 벡터 데이터베이스 (ChromaDB)
    CHROMA_DB_PATH: str = ""

    # ── 보안 및 인증 ────────────────────────────────────────────────────────
    # JWT 시크릿 키 (FarmOS-ShoppingMall 공유 인증)
    JWT_SECRET_KEY: str = ""

    # CORS 허용 도메인 (JSON 배열 형식)
    # 프론트엔드 → 백엔드 API 호출 허용
    CORS_ORIGINS: list[str] = []

    # ── 외부 API (공공데이터/지도) ──────────────────────────────────────────
    # 기상청 API (단기예보 등)
    # 기상청 단기예보 서비스 (지역 날씨 오케스트레이션용)
    KMA_DECODING_KEY: str = ""

    # 국가농작물병해충관리시스템 (NCPMS)
    NCPMS_API_KEY: str = ""

    # 농약안전정보시스템 
    PESTICIDE_API_KEY: str = ""

    # 식품안전나라
    # 식품의약품안전처 공공데이터활용 — 농약 등록정보(I1910) 조회에 사용
    # 회원가입 후 Open-API 이용신청 → 인증키 발급
    FOOD_SAFETY_API_KEY: str = ""

    # 농산물유통정보 (KAMIS)
    KAMIS_API_KEY: str = ""
    KAMIS_CERT_ID: str = ""

    # 카카오 REST API (위도 및 경도 변환)
    KAKAO_REST_API_KEY: str = ""

    # ── LLM & AI 서비스 ──────────────────────────────────────────────────────
    # LiteLLM 프록시 / OpenRouter
    # LiteLLM 사용 모델 목록 -> gpt-5-nano, gpt-5-mini, gpt-oss-20b, gemma-4-31b-it
    LITELLM_API_KEY: str = ""
    LITELLM_URL: str = ""
    LITELLM_MODEL: str = ""

    # Groq (Whisper STT)
    # 영농일지 서버사이드 음성 전사(STT)에 사용
    GROQ_API_KEY: str = ""
    GROQ_STT_URL: str = ""
    GROQ_STT_MODEL: str = ""

    # 리뷰 분석 및 기타 LLM 설정
    LLM_PROVIDER: str = ""
    LLM_MODEL: str = ""
    OLLAMA_BASE_URL: str = ""
    OLLAMA_REMOTE_URL: str = ""

    EMBED_MODEL: str = ""
    EMBED_DIM: int = 1024

    # LLM 리즈닝 강도 (GPT-5 계열 reasoning 모델용)
    # minimal | low | medium | high  또는 "none"(파라미터 미전송)
    # non-reasoning 모델(gemma, gpt-oss 등)은 무시됨
    LLM_REASONING_EFFORT: str = ""

    # Review Embedding (LiteLLM 프록시 경유, VoyageAI 등)
    REVIEW_ANALYSIS_BATCH_SIZE: int = 40
    REVIEW_ANALYSIS_MAX_RETRIES: int = 2

    # ── AI Agent (IoT 제어) ──────────────────────────────────────────────────
    AI_AGENT_MODEL: str = ""
    AI_AGENT_LLM_INTERVAL: int = 300
    AI_AGENT_RULE_INTERVAL: int = 30

    # IoT Relay Server Bridge
    # AI Agent Action History Bridge (Relay → FarmOS 미러)
    # Relay 와 공유하는 시크릿. 비워두면 AI_AGENT_BRIDGE_ENABLED=true 라도 안전 비활성화된다.
    # 운영 환경에서는 절대 코드에 하드코딩하지 말고 반드시 환경변수/.env 로만 주입한다.
    # 실제 키는 반드시 .env / 환경변수(IOT_RELAY_API_KEY) 로 주입한다.
    # 빈 문자열이면 AI_AGENT_BRIDGE_ENABLED=True 라도 Bridge 는 안전하게 비활성화된다.
    IOT_RELAY_BASE_URL: str = ""
    IOT_RELAY_API_KEY: str = ""
    AI_AGENT_BRIDGE_ENABLED: bool = False
    AI_AGENT_MIRROR_TTL_DAYS: int = 30
    AI_AGENT_BACKFILL_PAGE_SIZE: int = 200

    # 센서 임계값
    SOIL_MOISTURE_LOW: float = 55.0
    SOIL_MOISTURE_HIGH: float = 70.0

    # ── 기타 설정 ────────────────────────────────────────────────────────────
    # 농장 위치 (기상청 격자좌표 기본값)
    FARM_NX: int = 84
    FARM_NY: int = 106

    # 한글 폰트 (PDF 생성용) — 저장소에 번들된 Pretendard(SIL OFL 1.1) 기본 사용.
    # 시스템 폰트 사용하려면 .env에서 절대 경로로 오버라이드 가능.
    FONT_PATH: str = str(_BUNDLED_FONTS_DIR / "Pretendard-Regular.ttf")
    FONT_BOLD_PATH: str = str(_BUNDLED_FONTS_DIR / "Pretendard-Bold.ttf")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
