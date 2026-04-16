# 쇼핑몰 백엔드 — Claude 레퍼런스 카드

포트 4000 | FastAPI + PostgreSQL + ChromaDB | 패키지: `uv`

---

## 코드 작성 규칙

### 환경변수 처리
- 환경변수는 각 파일에서 `os.getenv()`로 직접 읽지 않는다.
- **반드시** `app/core/config.py`의 `Settings` 클래스에 필드로 추가하고 `from app.core.config import settings`로 참조한다.
- 민감한 값(API 키, 시크릿 키, DB URL 등)은 기본값을 `""`으로 두고 실제 값은 `.env`에서만 제공한다.

### 경로 상수
경로를 하드코딩하지 말고 `from app.paths import ...` 사용.

```python
PROJECT_ROOT    # FarmOS/
LOG_DIR         # FarmOS/logs/
CHROMA_DB_PATH  # .../backend/chroma_data/
AI_DATA_DIR     # .../backend/ai/data/
POLICY_DOCS_DIR # .../backend/ai/docs/  (gitignore — 로컬에 PDF/DOCX 직접 배치)
```

---

## 챗봇 에이전트

tool_use 기반 에이전트. Primary LLM 장애 시 Claude로 자동 전환.

```
OpenAIAgentClient (PRIMARY_LLM_*)
  → 실패 시 ClaudeAgentClient (ANTHROPIC_API_KEY)
    → 둘 다 실패 시 escalated=True
```

### 핵심 파일 맵

| 파일 | 역할 |
|------|------|
| `ai/agent/clients/openai.py` | Primary LLM — OpenAI 호환 (OpenRouter/Ollama/OpenAI 등) |
| `ai/agent/clients/claude.py` | Fallback LLM — Anthropic SDK |
| `ai/agent/clients/base.py` | 클라이언트 추상 인터페이스 |
| `ai/agent/executor.py` | 에이전트 루프, RequestContext, TraceStep |
| `ai/agent/tools.py` | TOOL_DEFINITIONS 12개 (중립 JSON Schema, HitL 도구 3개 포함) |
| `ai/agent/holiday.py` | 공휴일 API + 월별 캐시 |
| `ai/agent/prompts.py` | 에이전트 시스템 프롬프트 |
| `ai/rag.py` | retrieve() / retrieve_multiple() + distance_threshold 필터 |
| `ai/llm_client.py` | Ollama 클라이언트 — 리포트/비용분류 전용 (에이전트와 무관) |
| `ai/seed_rag.py` | ChromaDB 데이터 적재 |
| `app/core/config.py` | Settings 클래스 — 전체 환경변수 관리 |
| `app/paths.py` | 경로 상수 |
| `app/services/agent_chatbot.py` | AgentChatbotService |
| `app/routers/chatbot.py` | POST /api/chatbot/ask?debug=true |
| `app/schemas/chatlog.py` | TraceStepSchema, ChatAnswer |
| `app/main.py` | 에이전트 초기화 + UTF-8 로그 핸들러 |

### 보안 규칙

`get_order_status` 호출 시 LLM이 생성한 `user_id`는 반드시 제거하고 서버 세션 값 주입:
```python
args.pop("user_id", None)
await self._tool_get_order_status(db, user_id, **args)
```

### TraceStep

- `FarmOS/logs/chatbot.log` — INFO 레벨 항상 기록
- `POST /api/chatbot/ask?debug=true` — 응답 `trace` 필드에 포함

---

## 환경변수 (.env)

| 변수 | 설명 |
|------|------|
| `DATABASE_URL` | PostgreSQL 접속 URL |
| `JWT_SECRET_KEY` | FarmOS 공유 JWT 시크릿 |
| `OLLAMA_BASE_URL` | Ollama 서버 주소 — 임베딩 전용 (기본: `http://localhost:11434`) |
| `OLLAMA_EMBED_MODEL` | ChromaDB 임베딩 모델 |
| `UTILITY_LLM_BASE_URL` | 리포트/비용분류용 LLM 엔드포인트 (Ollama·OpenRouter 모두 가능) |
| `UTILITY_LLM_API_KEY` | 리포트/비용분류용 LLM API 키 |
| `UTILITY_LLM_MODEL` | 리포트/비용분류용 LLM 모델명 |
| `PRIMARY_LLM_BASE_URL` | 에이전트 Primary LLM 엔드포인트 (Ollama·OpenRouter 모두 가능) |
| `PRIMARY_LLM_API_KEY` | Primary LLM API 키 |
| `PRIMARY_LLM_MODEL` | Primary LLM 모델명 |
| `ANTHROPIC_API_KEY` | Fallback LLM — 없으면 폴백 비활성화 |
| `CLAUDE_FALLBACK_MODEL` | Claude Fallback 모델 (기본: `claude-haiku-4-5`) |
| `AGENT_MAX_ITERATIONS` | 에이전트 최대 반복 횟수 (기본: `10`) |
| `ANNIVERSARY_API_KEY` | 공공데이터포털 공휴일 API 키 |
| `POLICY_DOCS_DIR` | 정책 문서 폴더 (기본: `ai/docs/`, gitignore — 로컬 배치 필요) |

Provider 전환은 `PRIMARY_LLM_*` 세 값만 교체하면 됩니다. 자세한 예시는 `ai/agent/clients/README.md` 참고.

---

## 자주 쓰는 명령

```bash
# 서버 실행
uv run uvicorn app.main:app --reload --port 4000

# RAG 시딩 + 검증
uv run python scripts/seed_and_verify.py

# 테스트
uv run pytest

# 챗봇 API 테스트
curl -X POST http://localhost:4000/api/chatbot/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"딸기 재고 있어?","session_id":null,"history":[]}'

# 추론 과정 확인
curl -X POST "http://localhost:4000/api/chatbot/ask?debug=true" \
  -H "Content-Type: application/json" \
  -d '{"question":"주문 배송 언제와?","session_id":null,"history":[]}'
```

---

## 상세 문서

| 위치 | 내용 |
|------|------|
| `ai/README.md` | AI 모듈 전체 구조 |
| `ai/agent/README.md` | 에이전트 도구 목록, RequestContext |
| `ai/agent/clients/README.md` | LLM 클라이언트, provider 전환 예시 |
| `app/core/README.md` | Settings 필드 전체 목록 |
| `app/services/README.md` | 서비스 레이어 구조 |
| `/chatbot-agent` 스킬 | 챗봇 에이전트 전체 기획 문서 |
