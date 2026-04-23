# FarmOS Backend Architecture

<!-- Code Sync: 2026-04-23 -->

## 기술 스택

| 항목 | 기술 | 버전 |
|------|------|------|
| 언어 | Python | 3.12 |
| 패키지 관리 | uv | 0.11.2 |
| 웹 프레임워크 | FastAPI | 0.135.2 |
| 설정 관리 | pydantic-settings | 2.13.1 |
| ASGI 서버 | uvicorn | 0.42.0 |
| 데이터 저장 (인증 / 쇼핑몰 / AI 판단 미러) | PostgreSQL 18 | asyncpg |
| IoT 센서·관수·알림 SSoT | **N100 Relay 전용 `iot-postgres` 컨테이너 (`iotdb`)** | Relay asyncpg |
| Vector DB (리뷰 임베딩) | ChromaDB (LiteLLM → Voyage v3.5) | 컬렉션 `reviews_voyage_v35` |
| SSE (임베딩/분석 진행률) | sse-starlette | `EventSourceResponse` |

> **2026-04-21**: FarmOS 로컬 DB 의 `iot_sensor_readings` / `iot_sensor_alerts` / `iot_irrigation_events` 테이블과 `/api/v1/sensors*` · `/api/v1/irrigation/*` 엔드포인트는 **완전 제거**됐다. 아래 §IoT PostgreSQL 저장소 / §API 엔드포인트 / §자동 관개 트리거 / §데이터 흐름 섹션은 **레거시 기록**으로, 현재 IoT 센서 데이터는 전적으로 Relay (`iot-postgres`) 가 SSoT 다. 상세 이전 경로는 `iot-relay-server-plan.md` 참조.
> **2026-04-20**: IoT 저장소를 인메모리(`deque` / `list`)에서 PostgreSQL로 전환 (Relay 측 패치 §iot-relay-server-postgres-patch.md).
> 접두사 규칙: 인증 `users`, 쇼핑몰 `shop_*`, AI 판단 미러 `ai_agent_*` (30일 TTL), 리뷰 분석 `review_analyses` / `review_sentiments`.

---

## 프로젝트 구조

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI 앱 (CORS, 라우터 등록)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # pydantic-settings 환경 설정
│   │   ├── database.py        # SQLAlchemy async engine + session
│   │   └── store.py           # IoT PostgreSQL 저장소 (SQLAlchemy async)
│   ├── models/
│   │   └── iot.py             # iot_sensor_readings / iot_irrigation_events / iot_sensor_alerts
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── sensor.py          # Pydantic 입력 스키마
│   └── api/
│       ├── __init__.py
│       ├── health.py          # GET /health
│       ├── sensors.py         # POST/GET 센서 데이터 + 알림
│       └── irrigation.py      # POST/GET 관개 제어
├── main.py                    # uvicorn 진입점
├── .env                       # 환경 변수
├── .env.example
├── .gitignore
├── pyproject.toml
└── uv.lock
```

---

## IoT PostgreSQL 저장소 (`app/core/store.py`) [LEGACY — 2026-04-21 제거됨]

> **LEGACY 기록**: 아래 설명은 2026-04-20 ~ 2026-04-21 짧은 기간 동안 FarmOS 로컬 BE 가 IoT 테이블을 보관했을 때의 내용이다. 2026-04-21 이후 로컬 IoT 테이블·라우터·모델은 `backend/scripts/drop_iot_legacy_tables.sql` 로 완전 제거됐고, IoT 데이터는 N100 Relay `iot-postgres` 가 유일한 SSoT 다. 이 섹션은 히스토리 참조 용도로만 남긴다.

3개 테이블을 SQLAlchemy 2.0 async ORM으로 다뤘다. 모델 정의는 `app/models/iot.py` (제거됨).

| 테이블 | 주요 컬럼 | 설명 |
|--------|----------|------|
| `iot_sensor_readings` | device_id, timestamp, soil/temp/humidity/light | 센서 시계열. `timestamp DESC` 인덱스로 최신 N건 조회 |
| `iot_irrigation_events` | triggered_at, valve_action, auto_triggered | 관개 밸브 이벤트 (자동/수동) |
| `iot_sensor_alerts` | type, severity, timestamp, resolved | 임계치 초과 알림 |

> 기동 시 `init_db()` 가 `CREATE TABLE IF NOT EXISTS` 로 멱등 생성한다.
> 토양 습도 시간 관성 상태(`_prev_soil_moisture`)는 파생값이므로 프로세스 스코프에 유지하고 DB에 저장하지 않는다.
> 저장소 함수는 모두 async — 호출부는 `db: AsyncSession = Depends(get_db)` 로 세션을 주입받는다.

---

## API 엔드포인트

Base URL: `/api/v1`

### Health

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 + IoT 테이블 건수 |

응답 예시:
```json
{
  "status": "ok",
  "storage": "postgres",
  "readings_count": 150,
  "irrigation_events_count": 2,
  "alerts_count": 3
}
```

### Sensors / Irrigation [LEGACY — 2026-04-21 제거됨]

> 이 엔드포인트들은 FarmOS BE 에서 제거됐다. 현재 FE(`useSensorData.ts`) 는 Relay (`http://iot.lilpa.moe:9000/api/v1/sensors*`, `/irrigation/*`) 를 직접 호출한다. 계약 명세는 `iot-relay-server-plan.md §4.1` 참조.

### Review Analysis (`/reviews/*`, 2026-04-10 이후)

| 메서드 | 경로 | 설명 | 비고 |
|--------|------|------|------|
| `POST` | `/reviews/embed` | `shop_reviews` → ChromaDB 동기화 | `ReviewRAG.sync_from_db()` |
| `GET` | `/reviews/embed/stream` | SSE 임베딩 진행률 | 2026-04-23 추가 |
| `POST` | `/reviews/analyze` | LLM 3가지 분석 실행 | 감성/키워드/요약 |
| `GET` | `/reviews/analyze/stream` | SSE 분석 진행률 + 중간 결과 | 층화 샘플링 (200, 최대 10000) |
| `GET` | `/reviews/analysis` | 최신 분석 결과 | |
| `POST` | `/reviews/search` | RAG 의미 검색 | |
| `GET` | `/reviews/trends?period=weekly` | 트렌드/이상 탐지 | |
| `GET` | `/reviews/report/pdf?analysis_id=N` | PDF 다운로드 | fpdf2 + 한글 폰트 |
| `GET`/`PUT` | `/reviews/settings` | 자동 분석 설정 | 멀티테넌트/스케줄러 **Phase 2 연기** |

모두 세션 인증. 상세: `docs/iot-review-analysis-implementation.md`.

### AI Agent (agent-action-history, 2026-04-20)

| 메서드 | 경로 | 설명 | 파라미터 |
|--------|------|------|----------|
| `GET` | `/ai-agent/activity/summary` | 오늘/7일/30일 집계 | `range=today\|7d\|30d` |
| `GET` | `/ai-agent/decisions` | 판단 이력 목록 (cursor pagination) | `cursor`, `limit`, `control_type`, `source`, `priority`, `since` |
| `GET` | `/ai-agent/decisions/{id}` | 판단 단건 상세 | - |
| `GET` | `/ai-agent/activity/hourly` | 최근 N시간 시간별 집계 (그래프용) | `hours=1~168` |
| `GET` | `/ai-agent/bridge/status` | Bridge Worker 상태 (운영 가시성) | - |

모두 세션 인증(`Depends(get_current_user)`) 필요. 데이터 소스: `ai_agent_decisions` / `ai_agent_activity_daily` / `ai_agent_activity_hourly` 테이블 (Bridge 가 적재).

---

## AI Agent Bridge Worker (`app/services/ai_agent_bridge.py`)

> Feature: `agent-action-history` (2026-04-20)
> Role: N100 Relay 의 AI decisions 를 FarmOS Postgres 로 실시간 동기화 (원본 미러 + 일/시간 요약).

### 동작

```
lifespan 기동 (AI_AGENT_BRIDGE_ENABLED=True 일 때만)
  └─ AiAgentBridge.start() → asyncio.create_task
       └─ _run_loop()
            1. _backfill_since_last()  # FarmOS 최신 timestamp 이후 Relay pull
            2. _connect_and_stream()   # SSE /ai-agent/stream 상시 구독
            - 실패 시: backoff 1→2→4→8→16→32→60s, stop 신호까지 무한 재시도
```

### 멱등 UPSERT

| 테이블 | 전략 |
|--------|------|
| `ai_agent_decisions` | `INSERT ... ON CONFLICT (id) DO NOTHING` — SSE/backfill 중복 무해 |
| `ai_agent_activity_daily` | `ON CONFLICT (day, control_type) DO UPDATE` — count +1, by_source/by_priority `jsonb_set` 로 키별 +1, avg_duration_ms 가중 평균 |
| `ai_agent_activity_hourly` | 동일 패턴, `hour = date_trunc('hour', timestamp)` |

### 환경 변수

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `AI_AGENT_BRIDGE_ENABLED` | `False` | Worker on/off (Relay patch 미적용 시 안전을 위해 기본 off) |
| `IOT_RELAY_BASE_URL` | `http://localhost:9000` | Relay API base URL |
| `IOT_RELAY_API_KEY` | `farmos-iot-default-key` | Relay `X-API-Key` 헤더 값 |
| `AI_AGENT_MIRROR_TTL_DAYS` | `30` | 원본 미러 보존 기간 |
| `AI_AGENT_BACKFILL_PAGE_SIZE` | `200` | 기동 backfill page size |

### 상태 조회

`GET /api/v1/ai-agent/bridge/status` 로 `healthy`, `last_event_at`, `last_backfill_at`, `last_error`, `total_processed` 확인 가능. Bridge 비활성화 시 `enabled=false` 응답.

### 장애 격리

- Bridge 실패는 FarmOS BE 기동을 막지 않음 (`main.py` lifespan 에서 try/except).
- Bridge 가 다운되어도 기존 미러 데이터로 `/decisions` `/summary` 는 정상 응답 (fallback 없음, 정적 데이터만).
- Relay `/decisions` / `/stream` 404 (patch 미적용) 감지 시 조용히 backoff 루프에 위임.

---

## 데이터 흐름 [LEGACY — 현재는 Relay 직결]

> 아래 다이어그램은 2026-04-20 FarmOS 로컬 BE 가 IoT 중계를 겸했을 때의 흐름이다. 현재(2026-04-23)는 다음과 같다:
>
> ```
> ESP8266 ── POST ──▶ N100 Relay (iot-postgres) ── SSE/GET ──▶ React 프론트
>                               │
>                               └── AI decision ── SSE/GET ──▶ FarmOS BE (ai_agent_bridge → ai_agent_decisions mirror) ──▶ FE
> ```

```
┌─────────────────┐     HTTP POST       ┌──────────────────┐     GET        ┌──────────────┐
│   ESP8266        │ ──────────────────→ │  FastAPI          │ ────────────→ │  React 프론트  │
│   DHT11 (온습도)  │  /api/v1/sensors   │  PostgreSQL       │  /latest     │  IoTDashboard │
│   포토레지스터    │  (snake_case)       │  (iot_* tables)   │  /history    │  Page.tsx     │
│   토양습도센서    │                     │                   │  (camelCase) │              │
└─────────────────┘                     └──────────────────┘              └──────────────┘
```

---

## ESP8266 POST 페이로드 (snake_case)

```json
{
  "device_id": "farmos-esp-001",
  "timestamp": "2026-03-15T14:30:00Z",
  "sensors": {
    "temperature": 22.5,
    "humidity": 65.3,
    "soil_moisture": 58.2,
    "light_intensity": 340
  }
}
```

## 프론트엔드 응답 (camelCase)

```json
{
  "timestamp": "2026-03-15T14:30:00Z",
  "soilMoisture": 58.2,
  "temperature": 22.5,
  "humidity": 65.3,
  "lightIntensity": 340
}
```

snake→camelCase 변환은 `store.py`의 `add_reading()`에서 저장 시점에 처리한다.

---

## 자동 관개 트리거 로직 [LEGACY — Relay 로 이관]

> FarmOS `/sensors` POST 는 제거됐다. 자동 관개 규칙(`soil_moisture < 55%` → IrrigationEvent + Alert, `humidity > 90%` → Alert)은 현재 Relay `iot_relay_server/app/store.py` 에 이식되어 있다.

레거시 동작 (FarmOS BE): `POST /api/v1/sensors` 수신 시 자동 실행:

| 조건 | 동작 |
|------|------|
| `soil_moisture < 55%` | `IrrigationEvent(열림)` + `SensorAlert(경고)` 자동 생성 |
| `humidity > 90%` | `SensorAlert(주의, "병해 발생 위험")` 자동 생성 |

임계값은 `.env`의 `SOIL_MOISTURE_LOW`, `SOIL_MOISTURE_HIGH`로 조정.

---

## 환경 변수 (.env)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `CORS_ORIGINS` | `["http://localhost:5173"]` | 허용 CORS 도메인 |
| `SOIL_MOISTURE_LOW` | `55.0` | 관개 트리거 하한 (%) |
| `SOIL_MOISTURE_HIGH` | `70.0` | 관개 중단 상한 (%) |

---

## 실행 방법

```bash
cd backend

# 서버 실행 (hot reload)
uv run python main.py

# Swagger 문서
# http://localhost:8000/docs
```

PostgreSQL `farmos` DB가 필요하다. 테이블은 서버 시작 시 자동 생성된다.

---

## 프론트엔드 연동 가이드

현재 프론트엔드(`IoTDashboardPage.tsx`)는 Mock 데이터를 사용 중. 실제 API로 전환하려면:

1. `src/hooks/useSensorData.ts` 커스텀 훅 생성 (fetch polling)
2. `IoTDashboardPage.tsx`에서 Mock import를 훅으로 교체
3. `.env`에 `VITE_API_URL=http://localhost:8000/api/v1` 추가
4. `VITE_USE_MOCK_SENSORS=true/false`로 Mock/실제 모드 전환
