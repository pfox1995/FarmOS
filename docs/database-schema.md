# FarmOS Database Schema

## 데이터베이스 정보

| 항목 | 값 |
|------|-----|
| DBMS | PostgreSQL 18 |
| 데이터베이스명 | farmos |
| 접속 | postgres:root@localhost:5432 |
| ORM | SQLAlchemy 2.0 (async) |
| 드라이버 | asyncpg |

---

## 저장소 구분

<!-- Code Sync: 2026-04-23 -->

| 영역 | 저장 방식 | 사유 |
|------|----------|------|
| 사용자 인증 | **PostgreSQL** (`users`) | 영속 데이터 |
| IoT 센서 / 관수 / 알림 | **N100 Relay 전용 `iot-postgres` 컨테이너 (`iotdb`)** | 2026-04-21 이후 FarmOS 로컬 DB 에서 제거. Relay 가 SSoT. |
| AI 판단 (원본) | Relay `iotdb` (`iot_agent_decisions`) | Relay 가 canonical source |
| AI 판단 (미러) | FarmOS `farmos` DB (`ai_agent_decisions` + `ai_agent_activity_daily/hourly`) | 최근 30일 mirror + 집계 |
| 리뷰 분석 결과 | FarmOS `farmos` DB (`review_analyses`, `review_sentiments`) | 영속 |
| 리뷰 임베딩 벡터 | **ChromaDB** (컬렉션 `reviews_voyage_v35`, 1024-dim) | PostgreSQL 밖, 디스크 persistent store |
| 쇼핑몰 | **PostgreSQL** (`shop_` 접두사 테이블) | FarmOS와 동일 DB 공유 |

> **2026-04-21**: FarmOS `farmos` DB 의 `iot_*` 테이블은 `backend/scripts/drop_iot_legacy_tables.sql` 로 **완전 제거**됐다. 아래 §IoT 테이블 섹션은 **Relay 측 `iotdb` 의 스키마 레퍼런스**로만 유효하다 (Relay 는 같은 DDL 유지).
> AI 판단 데이터는 Relay 가 원본, FarmOS 가 미러(30일 TTL) + 일/시간 요약을 Bridge Worker 로 동기화.
> N100 `iot-postgres` 는 기존 운영 중인 다른 Postgres 와 네트워크/볼륨/자격증명이 완전히 분리된 전용 인스턴스다.

---

## 테이블: `users`

> 모델 파일: `backend/app/models/user.py`

| 설명 | Python Field | SQL Type |
| --- | --- | --- |
| 이름 | name | VARCHAR(10) (사람이름) |
| 아이디 | id | VARCHAR(10) (clover0309) |
| 비밀번호 | password | VARCHAR(255) (password111) Bcrypt 해싱처리 |
| 이메일 | email | EMAIL (clover0309@github.com) |
| 지역 | location | VARCHAR(10) (경기도 안산시) |
| 면적 | area | FLOAT (33.2) |
| 농장이름 | farmname | VARCHAR(40) (김사과 사과농장) |
| 프로필사진 | profile | VARCHAR(255) (s3.amazon.com/dfjkalsdjkasdlfl) |
| 계정 생성 날짜 | create_at | DATE (2026/04/01) |
| 상태 | status | INT (1) (0 탈퇴, 1 정상) |

### 시딩 데이터

| user_id | name | phone | email | password | farm_name | region |
|---------|------|-------|-------|----------|-----------|--------|
| farmer01 | 김사과 | 010-1234-5678 | farmer01@farmos.kr | farm1234 | 김사과 사과농장 | 경북 영주시 |
| parkpear | 박배나무 | 010-9876-5432 | parkpear@farmos.kr | pear5678 | 박씨네 배 과수원 | 충남 천안시 |

---

## IoT 테이블 (`iot_` 접두사) — Relay `iotdb` 전용

<!-- Code Sync: 2026-04-23 — FarmOS 로컬 DB 에서 제거됨. Relay 만 보유. -->

> **주의**: 2026-04-21 이후 FarmOS `farmos` DB 에는 `iot_*` 테이블이 존재하지 않는다. 아래 DDL 은 현재 **N100 Relay `iot-postgres` 컨테이너 / `iotdb` DB** 에만 적용된 상태다. 관련 소스는 `iot_relay_server/app/store.py` (asyncpg), DDL 원본은 `iot_relay_server/iot_init.sql` 또는 `docs/iot-relay-server-postgres-patch.md §1`.
> 이전 모델 파일: `backend/app/models/iot.py` (삭제됨), `backend/app/core/store.py` (레거시 경로 제거됨).

### `iot_sensor_readings`

| 컬럼 | SQL Type | Null | 설명 |
|------|----------|:----:|------|
| id | VARCHAR(36) PK | NO | UUID4 |
| device_id | VARCHAR(64) | NO | ESP8266 식별자 (인덱스) |
| timestamp | TIMESTAMPTZ | NO | 센서 전송 시각 (인덱스, 조회 정렬 키) |
| soil_moisture | FLOAT | NO | 실측 또는 추정치 |
| temperature | FLOAT | NO |  |
| humidity | FLOAT | NO |  |
| light_intensity | INTEGER | NO |  |
| created_at | TIMESTAMPTZ | NO | `now()` default |

### `iot_irrigation_events`

| 컬럼 | SQL Type | Null | 설명 |
|------|----------|:----:|------|
| id | VARCHAR(36) PK | NO | UUID4 |
| triggered_at | TIMESTAMPTZ | NO | 이벤트 발생 시각 (인덱스) |
| reason | VARCHAR(255) | NO | 사유 |
| valve_action | VARCHAR(10) | NO | "열림" / "닫힘" |
| duration | INTEGER | NO | 지속 시간(초) |
| auto_triggered | BOOLEAN | NO | 자동 여부 |
| created_at | TIMESTAMPTZ | NO |  |

### `iot_sensor_alerts`

| 컬럼 | SQL Type | Null | 설명 |
|------|----------|:----:|------|
| id | VARCHAR(36) PK | NO | UUID4 |
| type | VARCHAR(32) | NO | "moisture" / "humidity" 등 |
| severity | VARCHAR(16) | NO | "경고" / "주의" |
| message | VARCHAR(255) | NO |  |
| timestamp | TIMESTAMPTZ | NO | 알림 시각 (인덱스) |
| resolved | BOOLEAN | NO | 기본 FALSE |
| resolved_at | TIMESTAMPTZ | YES | 해결 처리 시각 |
| created_at | TIMESTAMPTZ | NO |  |

> 이전 인메모리 구조(`deque[dict]` / `list[dict]`)는 2026-04-20 PostgreSQL로 전환됨.
> 토양 습도 시간 관성 값(`_prev_soil_moisture`)은 영속화 대상이 아니며 프로세스 스코프로 유지.

---

## AI Agent 테이블 (`ai_agent_` 접두사)

> 모듈: `backend/app/models/ai_agent.py`
> ORM: SQLAlchemy 2.0 (async) + asyncpg 드라이버
> Feature: `agent-action-history` (2026-04-20)
> 역할: N100 Relay 원본 → FarmOS 최근 30일 mirror + 일/시간 요약. 실시간 동기화는 `AiAgentBridge` 워커(SSE + HTTP backfill).

### `ai_agent_decisions` (원본 미러, 최근 30일 TTL)

| 컬럼 | 타입 | NULL | 설명 |
|------|------|:----:|------|
| id | VARCHAR(36) | NO | Relay 가 생성한 UUID 를 그대로 PK 로 재사용 |
| timestamp | TIMESTAMPTZ | NO | AI 판단 시각 (index) |
| control_type | VARCHAR(32) | NO | ventilation\|irrigation\|lighting\|shading (index) |
| priority | VARCHAR(16) | NO | emergency\|high\|medium\|low |
| source | VARCHAR(16) | NO | rule\|llm\|tool\|manual (index) |
| reason | TEXT | NO | 판단 근거 문장 |
| action | JSONB | NO | 실제 제어 변경 payload (default `{}`) |
| tool_calls | JSONB | NO | 도구 호출 트레이스 배열 (default `[]`) |
| sensor_snapshot | JSONB | YES | 판단 시점 센서 스냅샷 |
| duration_ms | INTEGER | YES | 판단 소요 시간 |
| created_at | TIMESTAMPTZ | NO | FarmOS insert 시각 — cursor pagination 키 (index DESC) |

인덱스: `created_at DESC`, `timestamp DESC`, `control_type`, `source`.

### `ai_agent_activity_daily` (일별 집계)

| 컬럼 | 타입 | NULL | 설명 |
|------|------|:----:|------|
| day | DATE | NO | PK |
| control_type | VARCHAR(32) | NO | PK |
| count | INTEGER | NO | 해당 (day, control_type) 판단 건수 |
| by_source | JSONB | NO | `{"rule":12, "llm":3, ...}` |
| by_priority | JSONB | NO | `{"high":5, ...}` |
| avg_duration_ms | INTEGER | YES | 가중 평균 (count 기반) |
| last_at | TIMESTAMPTZ | YES | 마지막 판단 시각 |
| updated_at | TIMESTAMPTZ | NO | 집계 마지막 갱신 |

UPSERT 전략: Bridge 가 원본 INSERT 성공 시마다 `ON CONFLICT (day, control_type) DO UPDATE` 로 증분 갱신 (count +1, by_source/by_priority `jsonb_set` 로 키별 +1).

### `ai_agent_activity_hourly` (시간별 집계)

| 컬럼 | 타입 | NULL | 설명 |
|------|------|:----:|------|
| hour | TIMESTAMPTZ | NO | `date_trunc('hour', timestamp)` (PK) |
| control_type | VARCHAR(32) | NO | PK |
| count | INTEGER | NO |  |
| by_source | JSONB | NO |  |
| by_priority | JSONB | NO |  |
| last_at | TIMESTAMPTZ | YES |  |
| updated_at | TIMESTAMPTZ | NO |  |

인덱스: `hour DESC`. 용도: 최근 48h 그래프.

> **데이터 정합성**: `ai_agent_decisions` (원본) 이 canonical source. daily/hourly 는 Bridge 가 장애로 누락된 경우 원본에서 재빌드 가능 (운영 스크립트는 추후 작성).
>
> **TTL**: `ai_agent_decisions` 는 `AI_AGENT_MIRROR_TTL_DAYS=30` (default). 야간 배치로 `DELETE WHERE created_at < now() - INTERVAL '30 days'` 수행 예정 (현재 수동 또는 Bridge 에 후속 구현).

---

## 리뷰 분석 테이블 (`review_analyses`, `review_sentiments`)

<!-- Code Sync: 2026-04-23 -->

> 모델: `backend/app/models/review_analysis.py`
> Pydantic 스키마: `backend/app/schemas/review_analysis.py`
> 생성: FastAPI 기동 시 `Base.metadata.create_all` 로 자동 생성.

### `review_analyses` (분석 실행 기록)

| 컬럼 | 타입 | NULL | 설명 |
|------|------|:----:|------|
| id | SERIAL | NO | PK |
| analysis_type | VARCHAR(20) | NO | `manual` \| `batch` (현재 `batch` 미사용 — Phase 2 연기) |
| target_scope | VARCHAR(50) | NO | `all` \| `product:{id}` \| `platform:{name}` |
| review_count | INTEGER | NO | 분석 대상 리뷰 총 건수 (샘플링 전 전체) |
| sentiment_summary | JSONB | YES | `{positive, negative, neutral, total}` |
| keywords | JSONB | YES | `[{word, count, sentiment}]` |
| summary | TEXT | YES | 3-part 요약 JSON 문자열 (`overall` / `positives` / `negatives` / `suggestions`) |
| trends | JSONB | YES | 주간/이상 탐지 결과 |
| anomalies | JSONB | YES | `[{type, week, message, severity}]` |
| llm_provider | VARCHAR(30) | YES | `OllamaClient` / `OpenRouterClient` / `RemoteOllamaClient` |
| llm_model | VARCHAR(50) | YES | `llama3`, `openai/gpt-4o-mini` 등 |
| processing_time_ms | INTEGER | YES |  |
| created_at | TIMESTAMPTZ | NO | `now()` default |

### `review_sentiments` (개별 리뷰 감성 캐시)

| 컬럼 | 타입 | NULL | 설명 |
|------|------|:----:|------|
| id | SERIAL | NO | PK |
| review_id | VARCHAR(50) | NO | ChromaDB 리뷰 ID (외부 키 없음, 논리적 참조) |
| sentiment | VARCHAR(10) | NO | `positive` \| `negative` \| `neutral` |
| score | FLOAT | YES | 0.0 ~ 1.0 신뢰도 |
| reason | TEXT | YES | LLM 판단 근거 |
| keywords | JSONB | YES | 리뷰별 키워드 |
| analyzed_at | TIMESTAMPTZ | NO | `now()` default |

> ChromaDB 벡터는 별도 저장. 컬렉션: `reviews_voyage_v35` (1024-dim, LiteLLM → VoyageAI `voyage-3.5`). Migration history: §iot-review-analysis-implementation.md §2.1.

---

## 쇼핑몰 테이블 (`shop_` 접두사)

> 모듈: `shopping_mall/backend/app/models/`
> ORM: SQLAlchemy 2.0 (sync) + psycopg2 드라이버

| 테이블명 | 주요 필드 | 시드 건수 |
|----------|----------|:---------:|
| `shop_categories` | id, name, parent_id, icon, sort_order | 12 |
| `shop_stores` | id, name, description, rating, product_count | 5 |
| `shop_products` | id, name, price, discount_rate, category_id, store_id, stock | 42 |
| `shop_users` | id, name, email, phone, address | 5 |
| `shop_cart_items` | id, user_id, product_id, quantity | 5 |
| `shop_orders` | id, user_id, total_price, status, shipping_address | 10 |
| `shop_order_items` | id, order_id, product_id, quantity, price | 19 |
| `shop_reviews` | id, product_id, user_id, rating, content | 30 |
| `shop_wishlists` | id, user_id, product_id | 8 |
| `shop_shipments` | id, order_id, carrier, tracking_number, status | 5 |
| `shop_harvest_schedules` | id, product_id, harvest_date, estimated_quantity | 8 |
| `shop_revenue_entries` | id, date, order_id, product_id, total_amount | 15 |
| `shop_expense_entries` | id, date, description, amount, category | 10 |
| `shop_weekly_reports` | id, week_start, week_end, total_revenue, net_profit | 2 |
| `shop_customer_segments` | id, user_id, segment, recency_days, frequency, monetary | 5 |
| `shop_chat_logs` | id, user_id, intent, question, answer | 5 |
