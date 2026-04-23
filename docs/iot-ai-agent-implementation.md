# IoT AI Agent 구현 기록

> **작성일**: 2026-04-07
> **상태**: 구현 완료 (버그 수정 포함)
>
> **Code Sync 2026-04-23**: 이 문서는 초기 규칙+LLM JSON 판단 구조를 기록한다. 2026-04-14 Tool Calling 전환(§6 tools/ 패키지, §13 reasoning_trace) 이후 변경 사항은 본 문서에도 부분 반영되어 있으며, 상세한 전환 보고는 `docs/iot-ai-agent-tool-calling-report.md` 를 읽는다. FarmOS 측 판단 미러(`ai_agent_decisions`) 는 `docs/02-design/features/agent-action-history.design.md` 참고.

---

## 1. 개요

IoT 센서값 + 기상청 API를 종합 분석하여 환기/관수/조명/차광을 자동 제어하는 AI Agent 시스템.
모든 제어는 **가상 시뮬레이션** (실제 하드웨어 제어 없음).

---

## 2. 아키텍처

```
ESP8266 (DHT11 + CdS, 30초 간격)
    │ HTTP POST
    v
릴레이 서버 (N100:9000, Docker)
    ├─ store.py: 센서 저장 + 토양습도 추정
    ├─ sensor_filter.py: 조도센서 이상값 필터링
    ├─ ai_agent.py: 규칙 판단 + LLM 종합 판단
    ├─ weather_client.py: 기상청 API (또는 mock)
    └─ /api/v1/ai-agent/* 엔드포인트
          │ 30초 폴링
          v
    프론트엔드 대시보드 (AIAgentPanel)
```

---

## 3. 2단계 판단 구조

### 1단계: 규칙 기반 (항상 실행, LLM 비용 0)

#### 이상 상황 발동

| 조건 | 제어 | 우선순위 |
|------|------|---------|
| 온도 > 35C | 창문 100%, 팬 3000 RPM | emergency |
| 온도 30~35C + 외부 < 내부 | 자연환기 (비율 계산) | high |
| 습도 > 90% | 팬 1500 RPM, 창문 50%+ | high |
| 강수 감지 | 창문 닫기 | high |
| 토양수분 < 30% | 긴급 관수 3L | emergency |
| 야간 + 외부 < 5C | 보온커튼 100%, 창문 닫기 | emergency |
| 야간 + 외부 < 10C | 보온커튼 70%+ | medium |
| 야간 | 조명 OFF | low |
| 주간 + 조도 < 5,000 lux | 보광등 60% | medium |
| 주간 + 조도 > 70,000 lux | 차광막 50% | medium |

#### 정상 복귀

| 조건 | 제어 | 비고 |
|------|------|------|
| 온도 ≤ 30C + 습도 ≤ 80% | 환기 해제 (창문 0%, 팬 0) | 창문/팬 둘 다 체크 |
| 강수 종료 + 온도/습도 높음 | 창문 재개방 | 이력에서 강수 판단 확인 후만 |
| 토양수분 ≥ 50% | 관수 밸브 닫힘 | |
| 주간 | 보온커튼 해제 | |
| 주간 + 조도 ≥ 30,000 lux | 보광등 OFF | |
| 조도 ≤ 50,000 lux | 차광막 해제 | |

### 2단계: LLM (GPT-5-mini, 5분 간격)

- 센서값 5% 이상 변화 시에만 호출
- 긴급 아닌 미세 조정, 기상 예보 반영, 작물별 양액 배합
- `OPENROUTER_API_KEY` 미설정 시 건너뜀

---

## 4. 조도센서 불안정 대응 (sensor_filter.py)

KY-018 LDR이 간헐적으로 0값을 반환하는 문제 대응:

1. **이동평균 필터**: 최근 10회 값의 이동평균 대비 ±80% 급변 → suspicious
2. **연속 0값 카운트**:
   - 3회 미만 + 낮시간 → 이전 유효값으로 대체 (suspicious)
   - 3회 이상 + 낮시간 → 센서 장애 판정 (unreliable)
   - 야간 + 0 → 정상
3. **신뢰도 플래그**: reliable / suspicious / unreliable
4. LLM 프롬프트에 신뢰도 정보 포함 → 판단 가중치 조절

---

## 5. 기상 데이터 (weather_client.py)

- **KMA_DECODING_KEY 있음**: 기상청 초단기실황 API 호출 (10분 캐싱)
- **없음**: 센서 데이터 기반 mock 기상 데이터 자동 생성
- 격자좌표 변환 함수 포함 (Lambert Conformal Conic)

---

## 6. 파일 구조

### 릴레이 서버 (iot_relay_server/app/)

<!-- Code Sync: 2026-04-23 — tools/ 패키지, control_store.py 추가 반영 -->

| 파일 | 역할 |
|------|------|
| `config.py` | 설정 (AI_AGENT_MODEL=`gpt-5-mini`, KMA 키 등) |
| `sensor_filter.py` | 센서 이상값 필터링 |
| `weather_client.py` | 기상청 API 클라이언트 (+ mock 예보) |
| `ai_agent_prompts.py` | Tool Use 시스템/사용자 프롬프트 |
| `ai_agent.py` | Agent 엔진 (규칙 엔진 + LLM Tool Calling 루프, 상태관리, 이력, SSE broadcast) |
| `tools/definitions.py` | **(신규)** 8개 Tool JSON Schema 정의 (읽기 4 + 제어 4) |
| `tools/executor.py` | **(신규)** Tool 실행 디스패처 + 핸들러 |
| `control_store.py` | **(신규)** 수동 제어 인메모리 상태 + 파일 영속화 (`control_state.json`) |
| `control_routes.py` | **(신규)** `/api/v1/control/*` 5개 엔드포인트 |
| `schemas.py` | CropProfileIn, OverrideIn, ControlCommandIn, ControlReportIn 등 |
| `store.py` | 토양습도 추정 + `iot_sensor_readings/irrigation/alerts` asyncpg CRUD + SSE broadcast 공유 (`_broadcast`, `_sse_subscribers`) + `iot_agent_decisions` asyncpg CRUD (`add_agent_decision` 등) |
| `main.py` | `sensors_router` + `ai_agent_router` + `control_router` 등록, asyncpg Pool lifespan |

### 로컬 백엔드 (backend/app/)

> **2026-04-14 Tool Calling 전환**: 백엔드의 `core/ai_agent.py`·`core/ai_agent_prompts.py`·`api/ai_agent.py` **Agent 판단 로직**은 Relay 와의 중복 제거 차원에서 삭제되었다. 백엔드는 더 이상 LLM 을 직접 호출하지 않고, Relay 가 canonical source.
>
> **2026-04-20 agent-action-history**: 대신 백엔드는 Relay `ai_decision` 을 소비해 `ai_agent_decisions` 미러 테이블에 저장하는 **Bridge Worker** 와 **읽기 전용 API** 를 담당한다.

| 레이어 | 파일 | 역할 |
|--------|------|------|
| Services | `backend/app/services/ai_agent_bridge.py` | Relay SSE 구독 + HTTP backfill + 멱등 UPSERT + daily/hourly 요약 |
| Models | `backend/app/models/ai_agent.py` | `AiAgentDecision` / `AiAgentActivityDaily` / `AiAgentActivityHourly` |
| API | `backend/app/api/ai_agent.py` | `/api/v1/ai-agent/activity/summary`, `/decisions`, `/decisions/{id}`, `/bridge/status` (세션 인증) |
| Main | `backend/app/main.py` | `AI_AGENT_BRIDGE_ENABLED=True` 일 때 lifespan 에서 Bridge `asyncio.create_task` 로 start |

### 프론트엔드 (frontend/src/)

| 파일 | 역할 |
|------|------|
| `types/index.ts` | AIControlState, AIDecision, CropProfile 타입 |
| `hooks/useAIAgent.ts` | 30초 폴링, toggle/updateProfile/override |
| `modules/iot/AIAgentPanel.tsx` | 4대 제어 카드 + 판단 이력 + ON/OFF |
| `modules/iot/CropProfileModal.tsx` | 프리셋 5종 + 자유 입력 모달 |
| `modules/iot/IoTDashboardPage.tsx` | AIAgentPanel 통합 |

---

## 7. API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/ai-agent/status` | Agent 상태 + 제어값 + 최신 판단 |
| GET | `/api/v1/ai-agent/decisions?limit=20` | 판단 이력 |
| POST | `/api/v1/ai-agent/toggle` | ON/OFF 전환 |
| GET | `/api/v1/ai-agent/crop-profile` | 작물 프로필 + 프리셋 |
| PUT | `/api/v1/ai-agent/crop-profile` | 작물 프로필 수정 |
| POST | `/api/v1/ai-agent/override` | 수동 오버라이드 |
| POST | `/api/v1/ai-agent/test-trigger` | 디버그: 수동 트리거 |

---

## 8. 작물 프리셋

| 작물 | 생육단계 | 적정온도 | 적정습도 | 일조 | N:P:K |
|------|---------|---------|---------|------|-------|
| 토마토 | 개화기 | 20~28C | 60~80% | 14h | 1.0:1.2:1.5 |
| 딸기 | 착과기 | 15~25C | 60~75% | 12h | 0.8:1.0:1.5 |
| 상추 | 영양생장기 | 15~22C | 60~70% | 12h | 1.5:0.8:1.0 |
| 고추 | 개화기 | 22~30C | 60~75% | 14h | 1.2:1.0:1.3 |
| 오이 | 영양생장기 | 20~28C | 70~85% | 13h | 1.3:1.0:1.2 |

---

## 9. 환경 설정 (.env)

```
# 기존
IOT_API_KEY=farmos-iot-default-key
SOIL_MOISTURE_LOW=55.0
SOIL_MOISTURE_HIGH=70.0

# AI Agent
OPENROUTER_API_KEY=          # 넣으면 LLM 판단 활성화
AI_AGENT_MODEL=openai/gpt-5-mini
AI_AGENT_LLM_INTERVAL=300   # LLM 호출 최소 간격 (초)

# 기상청 API (선택)
KMA_DECODING_KEY=            # 넣으면 실제 기상 데이터
FARM_NX=84                   # 격자좌표
FARM_NY=106
```

---

## 10. 발견된 버그 및 수정 이력

| 문제 | 원인 | 수정 |
|------|------|------|
| AI Agent가 아예 동작 안 함 | `store.py`(동기)에서 `asyncio.ensure_future()` 호출 실패, `except: pass`로 무시됨 | `main.py`의 async 엔드포인트에서 `await` 직접 호출로 변경 |
| 습도 정상인데 환기 계속 유지 | 정상 복귀 로직 없음 (발동만 있고 해제 없음) | 모든 제어 항목에 정상 복귀 규칙 추가 |
| 창문만 열린 상태 복귀 안 됨 | 복귀 조건이 `fan_speed > 0`만 체크 | `fan_speed > 0 OR window_open_pct > 0`으로 변경 |
| 강수 복귀 오발동 | 강수 이력 없는데도 매번 "강수 종료" 판단 실행 | 최근 이력에서 강수 판단이 있었을 때만 복귀 |
| `daily_total_L` 무한 누적 | 일일 리셋 로직 없음 | 자정(KST) 기준 0으로 리셋 |
| `soil_moisture` None 비교 에러 | `dict.get(key, 50)`이 값이 `None`일 때 기본값 적용 안 됨 | `or 50`으로 변경 (3곳) |
| AI Agent에 토양습도 추정값 미반영 | `sensors_dict` 원본(None)이 Agent에 전달됨 | `get_latest()`로 store 추정값 반영된 데이터 전달 |
| 프론트엔드 AI Agent 패널 안 보임 | `credentials: 'include'`가 릴레이 서버 CORS와 충돌 + API 실패 시 `return null` | `credentials: 'omit'` + 연결 대기 UI 표시 |
| 조명/차광 규칙 없음 | LLM에만 의존 | 조도 기반 보광등/차광막 규칙 추가 |

---

## 11. LLM 비용 관리

| 항목 | 전략 |
|------|------|
| 모델 | GPT-5-mini (경량, 저비용) |
| 호출 빈도 | 5분 간격 제한 + 센서값 5% 이상 변화 시에만 |
| 규칙 우선 | 긴급 상황은 LLM 없이 규칙으로 즉시 처리 |
| 키 미설정 시 | 규칙만으로 동작 (LLM 비용 0) |
| 예상 호출량 | 일 50~150회 (센서 변화량에 따라) |

---

## 12. 배포 방법

```bash
# N100 서버에서
cd iot_relay_server
git pull
docker-compose up -d --build
```

Docker 재빌드 시 새 파일(sensor_filter.py, weather_client.py, ai_agent.py 등)이 자동 포함됨.

---

## 13. reasoning_trace / tool_calls 정의 (2026-04-23 추가)

<!-- Code Sync: 2026-04-23 -->

Tool Calling 전환 이후 "reasoning trace" 라는 용어가 여러 장소(프롬프트, 모델, 프론트 UI) 에서 사용되므로 정의를 명확히 한다.

### 13.1 저장되는 것 / 저장되지 않는 것

| 항목 | 저장 위치 | 타입 | 저장 여부 |
|------|-----------|------|:--------:|
| 최종 `reason` 1~2문장 요약 | `iot_agent_decisions.reason` / `ai_agent_decisions.reason` | TEXT | ✅ |
| Tool 호출 순서·인자·result | `iot_agent_decisions.tool_calls` / `ai_agent_decisions.tool_calls` | JSONB 배열 | ✅ |
| 판단 시점 센서 스냅샷 | `sensor_snapshot` | JSONB | ✅ |
| `action` (실제 제어 변경 payload) | `action` | JSONB | ✅ |
| LLM 멀티턴 대화 히스토리 전체 (system/user/assistant turns) | — | — | ❌ 저장하지 않음 |
| LLM raw completion (tokens/logprobs/stop_reason 등) | — | — | ❌ 저장하지 않음 |

즉, **"reasoning_trace" 는 이 문서 맥락에서 `tool_calls` JSONB 배열을 가리킨다**. full LLM turn history 를 persist 하지 않는 이유는 (1) 토큰 수만큼 DB 비용이 선형 증가하고, (2) 30일 TTL(`AI_AGENT_MIRROR_TTL_DAYS`) 내에서 재구성 가치가 낮기 때문이다.

### 13.2 SSE broadcast 순서 불변식

```
[LLM 완료] → [iot_agent_decisions INSERT (reason + tool_calls + sensor_snapshot)]
           → [SSE broadcast("ai_decision", payload)]
```

- **persist 가 반드시 broadcast 보다 앞**에 있어야 한다.
- 이유: FarmOS Bridge 는 `ai_agent_decisions` 테이블에 `ON CONFLICT (id) DO NOTHING` 으로 UPSERT 한다. broadcast 가 먼저 도착해 Bridge 가 insert 하더라도, Relay 가 장애로 재시작하면 Bridge 의 backfill 호출(`GET /ai-agent/decisions?since=...`) 이 Relay DB 를 기준으로 하기 때문에 Relay persist 가 누락되면 `tool_calls` 가 영구 유실된다.
- 불변식 위반 예: `broadcast → (장애) → persist 미실행` 시, FarmOS 측 row 는 존재하지만 tool_calls 가 `[]` 상태가 될 수 있다.

이 규칙은 `iot-relay-server-postgres-patch.md` §10.4 와 `docs/02-design/features/agent-action-history.design.md` §2.2 의 Happy Path 를 구체화한 것이다.

### 13.3 프론트엔드 소비

- `AIDecisionDetailModal.tsx` 는 `tool_calls` 배열을 순번·도구명·arguments·result.success 로 렌더.
- `AIAgentPanel.tsx` 의 row 는 요약(`reason` 1줄 + SourceBadge `rule`/`llm`/`tool`/`manual`) 만 표시하고 트레이스 전체는 모달로 이동.
- `useSensorData.ts` SSE `ai_decision` 수신 → `_aiDecisionHandlers` 체인 → `useAIAgent` 훅이 목록 최상단에 prepend 및 `/activity/summary` 숫자 증가.

### 13.4 운영 관찰 포인트

- `/api/v1/ai-agent/bridge/status` 의 `last_event_at` 이 5분 이상 정체되면 SSE 연결 단절 또는 LLM 호출 중단 의심.
- Relay `iot_agent_decisions` 와 FarmOS `ai_agent_decisions` 의 건수 차이가 backfill TTL(`AI_AGENT_MIRROR_TTL_DAYS=30`) 이내에서 `±1` 를 초과하면 불변식 위반 징후.
