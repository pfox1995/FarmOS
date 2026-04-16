# app/core/

애플리케이션 전역 설정.

## 파일

| 파일 | 역할 |
|------|------|
| `config.py` | 환경변수를 한 곳에서 관리하는 `Settings` 클래스 |

## 규칙

환경변수는 각 파일에서 `os.getenv()`로 직접 읽지 않는다.
반드시 `Settings`에 필드로 추가하고 `from app.core.config import settings`로 참조한다.

```python
from app.core.config import settings

engine = create_engine(settings.database_url)
```

## Settings 필드 목록

| 필드 | 환경변수 | 설명 |
|------|----------|------|
| `database_url` | `DATABASE_URL` | PostgreSQL 접속 URL |
| `jwt_secret_key` | `JWT_SECRET_KEY` | FarmOS 공유 JWT 시크릿 |
| `ollama_base_url` | `OLLAMA_BASE_URL` | Ollama 서버 주소 (임베딩 전용) |
| `ollama_embed_model` | `OLLAMA_EMBED_MODEL` | ChromaDB 임베딩 모델 |
| `utility_llm_base_url` | `UTILITY_LLM_BASE_URL` | 리포트/비용분류용 LLM 엔드포인트 |
| `utility_llm_api_key` | `UTILITY_LLM_API_KEY` | 리포트/비용분류용 LLM API 키 |
| `utility_llm_model` | `UTILITY_LLM_MODEL` | 리포트/비용분류용 LLM 모델명 |
| `primary_llm_base_url` | `PRIMARY_LLM_BASE_URL` | 에이전트 Primary LLM 엔드포인트 |
| `primary_llm_api_key` | `PRIMARY_LLM_API_KEY` | Primary LLM API 키 |
| `primary_llm_model` | `PRIMARY_LLM_MODEL` | Primary LLM 모델명 |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | Claude Fallback API 키 |
| `claude_fallback_model` | `CLAUDE_FALLBACK_MODEL` | Claude Fallback 모델명 |
| `agent_max_iterations` | `AGENT_MAX_ITERATIONS` | 에이전트 최대 반복 횟수 |
| `anniversary_api_key` | `ANNIVERSARY_API_KEY` | 공공데이터 공휴일 API 키 |

민감한 값(API 키, 시크릿 키, DB URL)은 기본값을 `""`으로 두고 실제 값은 `.env`에서만 제공한다.
