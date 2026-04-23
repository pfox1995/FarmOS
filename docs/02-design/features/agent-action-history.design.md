# agent-action-history Design Document

> **Summary**: N100 Relay → FarmOS Postgres 를 SSE Bridge 로 잇고, FarmOS BE 에 원본 미러(30일) + 일/시간 요약 + 3 개 REST API 를 두며, 프론트 AIAgentPanel 에 요약 카드·더보기(cursor pagination)·상세 모달을 추가한다 (Option C — Pragmatic).
>
> **Project**: FarmOS - agent-action-history
> **Version**: 0.2.0
> **Author**: clover0309
> **Date**: 2026-04-20 (Code Sync: 2026-04-23)
> **Status**: **Production (implemented & verified)** — 2026-04-23 코드 기준 모든 Module 1~6 구현 완료. L1 26/26 PASS, L2 6/6 PASS, L3 2/3 PASS (§8.5 E2 SSE 실시간 테스트는 미구현, production 동작은 확인됨).
> **Planning Doc**: [agent-action-history.plan.md](../../01-plan/features/agent-action-history.plan.md)
> **Archive**: `docs/archive/2026-04/agent-action-history/` (plan/design/analysis/report 완료 스냅샷)

### Pipeline References

| Phase | Document | Status |
|-------|----------|--------|
| Phase 1 | [Schema Definition](../../database-schema.md) | 병행 업데이트 |
| Phase 4 | [API Spec](#4-api-specification) | 본 문서 §4 |
| Phase 6 | [UI Integration](#5-uiux-design) | 본 문서 §5 |

---

## Context Anchor

> Copied from Plan document. Ensures strategic context survives Design→Do handoff.

| Key | Value |
|-----|-------|
| **WHY** | Relay 메모리에만 있는 AI decisions 가 재시작 시 휘발되고 20 건 제한으로 상세 추적이 불가능하다. FarmOS 는 AI 활동에 대한 영속 기록·요약·감사 채널이 없다. |
| **WHO** | 김사과(Primary persona, 대시보드에서 AI 행동 확인·감사), 운영자/관리자(이력 조회·분쟁 확인), AI Agent 자신(과거 판단 회고용 RAG 컨텍스트). |
| **RISK** | (R1) SSE Bridge 가 Relay 재시작/네트워크 단절 시 decision 유실 — cursor + 기동 시 backfill. (R2) 양쪽 Postgres 간 중복 저장 — FarmOS 는 "미러 + 요약" 역할 한정. (R3) 고빈도 decision 시 Worker 백프레셔 — batch commit + 요약 증분. (R4) 서버 조작 금지(N100) — Relay 는 patch-spec 문서로 제공. |
| **SUCCESS** | (SC-1) Relay decision → FarmOS insert p95 < 5s. (SC-2) `/activity/summary` 가 type/source/priority 집계 반환. (SC-3) 더보기로 30 일까지 조회 가능, 20 건 제한 제거. (SC-4) 상세 모달에 reason/action JSON/tool_calls/sensor_snapshot/duration 표시. (SC-5) FarmOS 재시작 후에도 이전 decisions 유지. |
| **SCOPE** | IN: Relay `iot_agent_decisions` DDL + pagination/detail API (patch-spec), FarmOS 3 테이블·3 API·SSE Bridge Worker, FE 상세 모달·더보기·요약 카드. OUT: AI 판단 로직, LLM 모델, ESP8266, 알림 통합, RAG 인덱싱, Relay 전체 리팩터. |

---

## 1. Overview

### 1.1 Design Goals

- **영속성**: 재시작 후에도 모든 AI decision 이 FarmOS DB 에 남는다.
- **추적성**: 한 decision 에 대해 당시 센서 스냅샷·도구 호출 순서·action JSON 까지 UI 로 추적 가능.
- **저지연 요약**: 사전 집계 테이블로 30 일 range `/summary` p95 < 150 ms.
- **관심사 분리(Pragmatic)**: bridge/api/schema 를 각 1 파일로 유지하면서 책임 경계는 명확히.
- **안전한 점진 도입**: `AI_AGENT_BRIDGE_ENABLED=false` 기본값으로 Relay patch 선적용 전에도 메인 BE 기동 무해.

### 1.2 Design Principles

- **Single Source of Truth**: decision 원본의 `id` 는 Relay 에서 생성, FarmOS 는 그대로 재사용(PK).
- **At-Least-Once with Idempotent Upsert**: SSE + HTTP backfill 이중 채널 → `INSERT ... ON CONFLICT (id) DO NOTHING`.
- **Summary is Derived**: 집계 테이블은 언제든 원본에서 재계산 가능. 장애 시 수동 재빌드 스크립트 제공.
- **Layered Degradation**: Bridge 실패 → API 는 여전히 기존 미러 데이터로 응답. Relay 장애가 FE 에 전파되지 않음.
- **No Relay Code Change in this repo**: Relay 변경은 `docs/iot-relay-server-postgres-patch.md` §10 으로만.

---

## 2. Architecture Options (v1.7.0)

### 2.0 Architecture Comparison

| Criteria | Option A: Minimal | Option B: Clean | **Option C: Pragmatic** |
|----------|:-:|:-:|:-:|
| **Approach** | 기존 파일에 인라인 | 완전 레이어 분리 + Repository | 관심사별 단일 파일 |
| **New BE Files** | 2-3 | 8-10 | **4** |
| **Modified BE Files** | 4-5 | 3 | **3** |
| **New FE Components** | 1 | 4-5 | **2-3** |
| **Modified FE Files** | 3 | 5-6 | **3-4** |
| **Complexity** | Low | High | **Medium** |
| **Maintainability** | Medium(coupled) | High | **High** |
| **Effort** | Low | High | **Medium** |
| **Risk** | AIAgentPanel 역할 혼재 | 오버엔지니어링 | **균형** |
| **Test Isolation** | Low | Highest | **High enough** |
| **Recommendation** | Hotfix | 장기 대규모 | **중규모 신규 + 기존 자산 재사용** |

**Selected**: **Option C — Pragmatic** — **Rationale**: 현재 규모에 맞는 관심사 분리(bridge 단일 파일, api 단일 파일, 컴포넌트 2-3 분리)로 테스트 가능성과 유지보수성을 얻으면서, Option B 수준의 패키지·Repository 추상화 비용은 피한다. 기존 `AIAgentPanel` 을 대부분 보존해 회귀 범위도 최소화된다.

### 2.1 Component Diagram

```
┌────────────────────┐
│  ESP8266           │
└──────┬─────────────┘
       │ POST /sensors
       ▼
┌────────────────────────────────────┐
│  N100 Relay (iot-relay:9000)       │
│  ┌──────────────────┐              │
│  │ AI Engine        │── decision ─▶│── INSERT ──▶ iot-postgres
│  └──────────────────┘              │              iot_agent_decisions
│  SSE /api/v1/ai-agent/stream       │
│  REST /ai-agent/decisions?cursor   │
│  REST /ai-agent/decisions/{id}     │
└──────┬─────────────────────────────┘
       │  SSE ai_decision  +  HTTP backfill(since=)
       ▼
┌────────────────────────────────────────────────┐
│  FarmOS BE (FastAPI, uvicorn)                  │
│  ┌────────────────────────────┐                │
│  │ ai_agent_bridge (Worker)   │                │
│  │  - connect() SSE           │                │
│  │  - backfill_since(ts)      │                │
│  │  - upsert_decision()       │                │
│  │  - bump_summary(day, hr)   │                │
│  └──────────┬─────────────────┘                │
│             ▼                                  │
│       farmos DB                                │
│  ┌──────────────────────┐                      │
│  │ ai_agent_decisions   │ (30d TTL)            │
│  │ ai_agent_activity_   │                      │
│  │   daily / hourly     │                      │
│  └──────────────────────┘                      │
│  ┌────────────────────────────┐                │
│  │ API /api/v1/ai-agent/      │                │
│  │  - GET activity/summary    │                │
│  │  - GET decisions           │                │
│  │  - GET decisions/{id}      │                │
│  └──────────┬─────────────────┘                │
└─────────────┼──────────────────────────────────┘
              ▼
       ┌─────────────────────┐
       │  React Frontend     │
       │  useAIAgent()       │
       │  AIAgentPanel       │
       │   ├─ SummaryCards   │
       │   ├─ DecisionList   │
       │   └─ DetailModal    │
       └─────────────────────┘
```

### 2.2 Data Flow (Happy Path)

```
1. ESP8266 → POST /sensors (30s cycle)
2. Relay AI Engine 판단 → Relay DB INSERT iot_agent_decisions
3. Relay SSE 브로드캐스트: event:ai_decision data:{id,...}
4. FarmOS Bridge Worker 수신 → UPSERT ai_agent_decisions
5. Bridge Worker: UPSERT ai_agent_activity_hourly (hour, control_type)
6. Bridge Worker: UPSERT ai_agent_activity_daily  (day,  control_type)
7. FE 대시보드 로딩 → GET /api/v1/ai-agent/activity/summary?range=today
8. FE 목록 로딩      → GET /api/v1/ai-agent/decisions?limit=20
9. FE 더보기         → GET /api/v1/ai-agent/decisions?cursor=<last.created_at>&limit=20
10. FE row 클릭      → GET /api/v1/ai-agent/decisions/{id}
```

### 2.3 Data Flow (Failure / Recovery)

```
- Relay 재시작: Bridge SSE 연결 끊김 → exponential backoff (1→2→4→...→60s)
- 재접속 성공: Bridge 가 farmos 의 MAX(timestamp) 조회 → Relay GET /decisions?since=<ts>&limit=200 반복 호출 (backfill)
- 중복 id UPSERT 는 ON CONFLICT DO NOTHING 으로 스킵
- FarmOS 재시작: lifespan 시작 시 동일 backfill 루틴 실행 (실시간 SSE 연결 전 동기 수행)
```

### 2.4 Dependencies

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| Bridge Worker | httpx (async), asyncpg via SQLAlchemy | SSE 스트림 + DB 쓰기 |
| API Router | SQLAlchemy async session | 읽기 전용 쿼리 |
| Summary Table | Decisions 테이블(논리적, FK 없음) | 집계 derived |
| FE SummaryCards | `/activity/summary` | 오늘/7일/30일 탭 |
| FE DetailModal | `/decisions/{id}` | 단건 상세 |
| FE DecisionList | `/decisions?cursor` | 페이지네이션 |

---

## 3. Data Model

### 3.1 Entity Definition (TypeScript 대응)

```typescript
// 공통 상세 payload (Relay 와 FarmOS 동일 shape)
interface AIDecision {
  id: string;                           // UUID, Relay 생성
  timestamp: string;                    // ISO8601 (판단 시각)
  control_type: 'ventilation' | 'irrigation' | 'lighting' | 'shading';
  priority: 'emergency' | 'high' | 'medium' | 'low';
  source: 'rule' | 'llm' | 'tool' | 'manual';
  reason: string;                       // 한 줄 요약
  action?: Record<string, unknown>;     // 제어 변경 페이로드 (JSONB)
  tool_calls?: Array<{
    tool: string;
    arguments: Record<string, unknown>;
    result?: { success?: boolean; data?: unknown; error?: string };
  }>;
  sensor_snapshot?: {                   // 판단 당시 센서값
    temperature?: number;
    humidity?: number;
    light_intensity?: number;
    soil_moisture?: number;
    timestamp?: string;
  };
  duration_ms?: number;                 // 판단~실행 소요 (optional)
  created_at?: string;                  // DB insert 시각 (FarmOS 측 서버 시각)
}

interface ActivitySummary {
  range: 'today' | '7d' | '30d';
  total: number;
  by_control_type: Record<string, number>;
  by_source:       Record<string, number>;
  by_priority:     Record<string, number>;
  avg_duration_ms: number | null;
  latest_at: string | null;
  generated_at: string;
}

interface DecisionListResponse {
  items: AIDecision[];
  next_cursor: string | null;          // `created_at` ISO, null 이면 끝
  has_more: boolean;
}
```

### 3.2 Entity Relationships

```
iot_agent_decisions (Relay)  ──SSE/HTTP──▶  ai_agent_decisions (FarmOS, mirror)
                                                 │
                                                 ├── bumps ──▶ ai_agent_activity_daily  (day, control_type) PK
                                                 └── bumps ──▶ ai_agent_activity_hourly (hour, control_type) PK
```

### 3.3 Database Schema (FarmOS `farmos` DB)

```sql
-- 1) 원본 미러 (30일 TTL)
CREATE TABLE IF NOT EXISTS ai_agent_decisions (
  id               VARCHAR(36) PRIMARY KEY,
  timestamp        TIMESTAMPTZ NOT NULL,
  control_type     VARCHAR(32) NOT NULL,
  priority         VARCHAR(16) NOT NULL,
  source           VARCHAR(16) NOT NULL,
  reason           TEXT NOT NULL DEFAULT '',
  action           JSONB NOT NULL DEFAULT '{}'::jsonb,
  tool_calls       JSONB NOT NULL DEFAULT '[]'::jsonb,
  sensor_snapshot  JSONB,
  duration_ms      INTEGER,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ai_agent_decisions_created_desc
  ON ai_agent_decisions (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_ai_agent_decisions_timestamp_desc
  ON ai_agent_decisions (timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_ai_agent_decisions_ctype
  ON ai_agent_decisions (control_type);
CREATE INDEX IF NOT EXISTS ix_ai_agent_decisions_source
  ON ai_agent_decisions (source);

-- 2) 일별 집계
CREATE TABLE IF NOT EXISTS ai_agent_activity_daily (
  day             DATE NOT NULL,
  control_type    VARCHAR(32) NOT NULL,
  count           INTEGER NOT NULL DEFAULT 0,
  by_source       JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {"rule": 12, "llm": 3, ...}
  by_priority     JSONB NOT NULL DEFAULT '{}'::jsonb,
  avg_duration_ms INTEGER,
  last_at         TIMESTAMPTZ,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (day, control_type)
);

-- 3) 시간별 집계 (최근 48시간 그래프용)
CREATE TABLE IF NOT EXISTS ai_agent_activity_hourly (
  hour            TIMESTAMPTZ NOT NULL,   -- date_trunc('hour', timestamp)
  control_type    VARCHAR(32) NOT NULL,
  count           INTEGER NOT NULL DEFAULT 0,
  by_source       JSONB NOT NULL DEFAULT '{}'::jsonb,
  by_priority     JSONB NOT NULL DEFAULT '{}'::jsonb,
  last_at         TIMESTAMPTZ,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (hour, control_type)
);
CREATE INDEX IF NOT EXISTS ix_ai_agent_hourly_hour ON ai_agent_activity_hourly (hour DESC);
```

**SQLAlchemy 모델 요약 (`backend/app/models/ai_agent.py`)**:

```python
class AiAgentDecision(Base):
    __tablename__ = "ai_agent_decisions"
    id             = mapped_column(String(36), primary_key=True)
    timestamp      = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    control_type   = mapped_column(String(32), nullable=False, index=True)
    priority       = mapped_column(String(16), nullable=False)
    source         = mapped_column(String(16), nullable=False, index=True)
    reason         = mapped_column(Text, nullable=False, default="")
    action         = mapped_column(JSONB, nullable=False, default=dict)
    tool_calls     = mapped_column(JSONB, nullable=False, default=list)
    sensor_snapshot= mapped_column(JSONB, nullable=True)
    duration_ms    = mapped_column(Integer, nullable=True)
    created_at     = mapped_column(DateTime(timezone=True), nullable=False, default=_now_utc, index=True)

class AiAgentActivityDaily(Base):
    __tablename__ = "ai_agent_activity_daily"
    day           = mapped_column(Date, primary_key=True)
    control_type  = mapped_column(String(32), primary_key=True)
    count         = mapped_column(Integer, nullable=False, default=0)
    by_source     = mapped_column(JSONB, nullable=False, default=dict)
    by_priority   = mapped_column(JSONB, nullable=False, default=dict)
    avg_duration_ms = mapped_column(Integer, nullable=True)
    last_at       = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at    = mapped_column(DateTime(timezone=True), nullable=False, default=_now_utc)

class AiAgentActivityHourly(Base):
    __tablename__ = "ai_agent_activity_hourly"
    hour          = mapped_column(DateTime(timezone=True), primary_key=True)
    control_type  = mapped_column(String(32), primary_key=True)
    count         = mapped_column(Integer, nullable=False, default=0)
    by_source     = mapped_column(JSONB, nullable=False, default=dict)
    by_priority   = mapped_column(JSONB, nullable=False, default=dict)
    last_at       = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at    = mapped_column(DateTime(timezone=True), nullable=False, default=_now_utc)
```

### 3.4 UPSERT 쿼리 샘플

```sql
-- 원본 미러
INSERT INTO ai_agent_decisions (id, timestamp, control_type, priority, source,
        reason, action, tool_calls, sensor_snapshot, duration_ms)
VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10)
ON CONFLICT (id) DO NOTHING;

-- 일별 집계
INSERT INTO ai_agent_activity_daily (day, control_type, count, by_source, by_priority,
        avg_duration_ms, last_at, updated_at)
VALUES ($day, $ct, 1, jsonb_build_object($src, 1), jsonb_build_object($pr, 1),
        $dur, $ts, now())
ON CONFLICT (day, control_type) DO UPDATE SET
  count       = ai_agent_activity_daily.count + 1,
  by_source   = jsonb_set(ai_agent_activity_daily.by_source, ARRAY[$src],
                  to_jsonb(COALESCE((ai_agent_activity_daily.by_source->>$src)::int, 0) + 1)),
  by_priority = jsonb_set(ai_agent_activity_daily.by_priority, ARRAY[$pr],
                  to_jsonb(COALESCE((ai_agent_activity_daily.by_priority->>$pr)::int, 0) + 1)),
  avg_duration_ms = CASE WHEN $dur IS NULL THEN ai_agent_activity_daily.avg_duration_ms
                         ELSE ((ai_agent_activity_daily.avg_duration_ms * ai_agent_activity_daily.count) + $dur)
                              / (ai_agent_activity_daily.count + 1) END,
  last_at     = GREATEST(ai_agent_activity_daily.last_at, $ts),
  updated_at  = now();
```

---

## 4. API Specification

### 4.0 Endpoint List

| Method | Path | Description | Auth |
|--------|------|-------------|:----:|
| GET | /api/v1/ai-agent/activity/summary | 오늘/7d/30d 집계 | Session |
| GET | /api/v1/ai-agent/decisions | 이력 목록 (cursor pagination) | Session |
| GET | /api/v1/ai-agent/decisions/{id} | 단건 상세 | Session |

> 기존 Relay 직접 호출(`https://iot.lilpa.moe/api/v1/ai-agent/*`) 은 FarmOS BE 경유로 전환.
> 동일 경로 유지로 FE 수정 최소화.

### 4.1 GET /api/v1/ai-agent/activity/summary

**Query Params**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| range | `today` \| `7d` \| `30d` | `today` | 집계 윈도우 |

**Response 200**:

```json
{
  "range": "today",
  "total": 47,
  "by_control_type": {"ventilation": 20, "irrigation": 15, "lighting": 8, "shading": 4},
  "by_source":       {"rule": 31, "llm": 12, "tool": 3, "manual": 1},
  "by_priority":     {"emergency": 2, "high": 10, "medium": 22, "low": 13},
  "avg_duration_ms": 412,
  "latest_at": "2026-04-20T08:41:13+09:00",
  "generated_at": "2026-04-20T08:41:45+09:00"
}
```

**계산 전략**:
- `today` / `7d` / `30d` 모두 `ai_agent_activity_daily` 에서 SUM/GROUP BY
- `today` 는 오늘 날짜 rows 만 (시간 단위가 필요하면 `ai_agent_activity_hourly` 추가 쿼리)

**Errors**: 400 invalid range, 500 internal.

### 4.2 GET /api/v1/ai-agent/decisions

**Query Params**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| cursor | ISO8601 | - | `created_at < cursor` |
| limit | int | 20 (max 100) | 반환 개수 |
| control_type | string | - | 필터 |
| source | string | - | 필터 |
| priority | string | - | 필터 |
| since | ISO8601 | - | `timestamp >= since` (그래프/재동기화용) |

**Response 200**:

```json
{
  "items": [
    {
      "id": "c2f…",
      "timestamp": "2026-04-20T08:41:13+09:00",
      "control_type": "ventilation",
      "priority": "high",
      "source": "llm",
      "reason": "CO2 450ppm, 내부 29도 → 창문 60% 개방",
      "action": {"window_open_pct": 60, "fan_speed": 1200},
      "tool_calls": [{"tool": "open_window", "arguments": {"pct": 60}, "result": {"success": true}}],
      "sensor_snapshot": {"temperature": 29.3, "humidity": 62.1, "light_intensity": 18400},
      "duration_ms": 388,
      "created_at": "2026-04-20T08:41:15+09:00"
    }
  ],
  "next_cursor": "2026-04-20T08:32:01+09:00",
  "has_more": true
}
```

**Errors**: 400 bad cursor/filter, 500 internal.

**쿼리**:

```sql
SELECT * FROM ai_agent_decisions
WHERE ($cursor IS NULL OR created_at < $cursor)
  AND ($ctype  IS NULL OR control_type = $ctype)
  AND ($src    IS NULL OR source = $src)
  AND ($pr     IS NULL OR priority = $pr)
  AND ($since  IS NULL OR timestamp >= $since)
ORDER BY created_at DESC
LIMIT $limit + 1;   -- has_more 판정
```

### 4.3 GET /api/v1/ai-agent/decisions/{id}

**Path Param**: `id` (UUID, 36 chars)

**Response 200**: 단일 `AIDecision` JSON (§3.1 과 동일).

**Errors**: 404 not found, 500 internal.

---

## 5. UI/UX Design

### 5.1 Screen Layout (AIAgentPanel)

```
┌──────────────────────────────────────────────────────────────┐
│ 🤖 AI Agent 제어              ● (status)  [⚙] [ON/OFF]      │
├──────────────────────────────────────────────────────────────┤
│ 🌿 방울토마토 / 성장기 / 적정 22~28°C                           │
├──────────────────────────────────────────────────────────────┤
│ [Tab: 오늘 | 7일 | 30일]                          ← §5.2 ①   │
│ ┌──────────┬──────────┬──────────┬──────────┐                │
│ │ Total    │ 환기 20  │ 관수 15  │ LLM 12   │                │
│ └──────────┴──────────┴──────────┴──────────┘                │
├──────────────────────────────────────────────────────────────┤
│ 4대 제어 카드 (기존 유지)                                     │
├──────────────────────────────────────────────────────────────┤
│ 📜 최근 판단 (47건)                               ← §5.2 ②   │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ 08:41  환기  [high][AI]    CO2 450ppm 창문 60% 개방   │   │
│ │ 08:32  관수  [med ][규칙]  토양수분 53% 임계치 이하   │   │
│ │ 08:12  조명  [low ][AI]    일출 이후 보조광 OFF       │   │
│ │ ... (5건씩 표시, row 클릭 → 상세 모달)                │   │
│ └────────────────────────────────────────────────────────┘   │
│                                 [더보기 ↓]        ← §5.2 ③   │
└──────────────────────────────────────────────────────────────┘

DetailModal (row 클릭 시)                          ← §5.2 ④
┌──────────────────────────────────────────────────────────────┐
│ 판단 상세                                              [Esc] │
├──────────────────────────────────────────────────────────────┤
│ 2026-04-20 08:41:13 · 환기 · high · AI                       │
│ "CO2 450ppm, 내부 29도 → 창문 60% 개방"                       │
├── [Action] ───────────────────────────────────────────────── │
│ { "window_open_pct": 60, "fan_speed": 1200 }       [Copy]    │
├── [Sensor Snapshot] ──────────────────────────────────────── │
│ temp 29.3°C  humidity 62.1%  light 18.4klx  soil 55.0%       │
├── [Tool Calls (1)] ───────────────────────────────────────── │
│ 1. open_window(pct=60) ✓ success                   [Copy]    │
├──────────────────────────────────────────────────────────────┤
│ duration 388ms · id c2f… · created_at 2026-04-20 08:41:15    │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 User Flow

1. 대시보드 진입 → SummaryCards 마운트 → `GET /activity/summary?range=today` → 탭 전환 시 재호출
2. 최근 판단 목록 초기 20 건 → `GET /decisions?limit=20`
3. "더보기" 클릭 → `GET /decisions?cursor=<last>&limit=20` → 누적 append
4. row 클릭 → DetailModal open → `GET /decisions/{id}` → JSON/Tool 트레이스/Snapshot 렌더
5. SSE `ai_decision` 이벤트 수신 → 목록 상단 prepend + 요약 카드 숫자 증가

### 5.3 Component List

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `AIAgentPanel` | `frontend/src/modules/iot/AIAgentPanel.tsx` | 전체 패널 컨테이너, 기존 구조 유지 + Summary/더보기 슬롯 삽입 |
| `AIActivitySummaryCards` | `frontend/src/modules/iot/AIActivitySummaryCards.tsx` | 신규. 오늘/7일/30일 탭, 카드 4개(total, top1 ctype, top1 source, avg duration) |
| `AIDecisionDetailModal` | `frontend/src/modules/iot/AIDecisionDetailModal.tsx` | 신규. 상세 모달. action/tool_calls/sensor_snapshot 렌더 + Copy 버튼 |
| `useAIAgent` | `frontend/src/hooks/useAIAgent.ts` | 수정. `API_BASE` 를 FarmOS BE 로, `fetchMore(cursor)` `fetchDetail(id)` `fetchSummary(range)` 추가 |
| `AIDecision` type | `frontend/src/types/index.ts` | `id` 필수화, `sensor_snapshot?`·`duration_ms?`·`created_at?` 추가 |

### 5.4 Page UI Checklist

#### IoT Dashboard → AIAgentPanel (수정)

- [ ] Element: 요약 카드 탭 3개 — `오늘`, `7일`, `30일` (ARIA `role="tablist"`, 선택 시 active 스타일)
- [ ] Element: 요약 카드 4칸 — `Total: N건`, `최다 제어 타입: <name> <count>`, `최다 소스: <name> <count>`, `평균 판단시간: <ms>ms`
- [ ] Element: 최근 판단 헤더 — 아이콘(📜) + "최근 판단" + 총 건수 표시
- [ ] Element: 판단 row — 시간, 제어 타입(환기/관수/조명/차광), PriorityBadge, SourceBadge, reason 1 줄 요약
- [ ] Interaction: row 전체 클릭 시 DetailModal open (기존 "도구 호출 N건" 버튼은 제거, 모달 내부로 이동)
- [ ] Button: `더보기 ↓` — `has_more === true` 일 때만 표시, 로딩 중 spinner
- [ ] Empty state: 이력 0 건일 때 "아직 판단 이력이 없습니다"
- [ ] Loading state: 초기 skeleton 유지

#### AIDecisionDetailModal (신규)

- [ ] Backdrop: `role="dialog" aria-modal="true"`, 배경 클릭 시 close
- [ ] Close: Esc 키, X 버튼, focus trap
- [ ] Header: 타임스탬프(`YYYY-MM-DD HH:mm:ss`), control_type 한글명, PriorityBadge, SourceBadge
- [ ] Section `Reason`: 전체 텍스트 (줄바꿈 보존)
- [ ] Section `Action`: JSON pretty (monospace) + Copy 버튼 (`navigator.clipboard.writeText`)
- [ ] Section `Sensor Snapshot`: 존재 시 4값 표 (temp/humid/light/soil) + 타임스탬프
- [ ] Section `Tool Calls (N)`: 순번, 도구명, arguments JSON, result success/fail 배지, 실패 시 error 문자열
- [ ] Footer: `duration_ms`, `id` (truncated + Copy), `created_at`
- [ ] No data 가드: 각 section 데이터 없으면 "없음" 표시

### 5.5 SSE 이벤트 반영

- 기존 `onAIDecisionEvent` 훅은 유지하되, 수신 payload 에 신규 필드(id/sensor_snapshot/duration_ms) 존재 시 그대로 반영.
- SummaryCards 는 수신 시 현재 탭이 `today` 인 경우에 한해 증분 계산(total + by_*), 아닐 때는 다음 탭 전환 시 서버에서 재fetch.

---

## 6. Error Handling

### 6.1 Error Code Definition

| Code | Message | Cause | Handling |
|------|---------|-------|----------|
| 400 | `INVALID_RANGE` | `range` 파라미터 잘못 | FE 에서 fallback `today` |
| 400 | `INVALID_CURSOR` | 파싱 불가 cursor | FE 에서 목록 초기화 재조회 |
| 404 | `DECISION_NOT_FOUND` | 해당 id 없음 | Modal 에 "삭제되었거나 30일이 지났습니다" 안내 후 자동 close |
| 502 | `RELAY_UPSTREAM_ERROR` | Bridge backfill 중 Relay 502/타임아웃 | 서버 로그만, FE 영향 없음 |
| 503 | `BRIDGE_DISABLED` | `AI_AGENT_BRIDGE_ENABLED=false` 인데 요청은 처리(읽기), 단 최근 데이터 없음 경고만 | FE 는 오래된 데이터 뱃지만 표시 |

### 6.2 Error Response Format (FarmOS 공통)

```json
{
  "error": {
    "code": "INVALID_RANGE",
    "message": "range must be one of today|7d|30d",
    "details": { "given": "1w" }
  }
}
```

### 6.3 Bridge 내부 예외 처리

| Event | Action |
|-------|--------|
| SSE 연결 실패 | backoff 1→2→4→8→16→32→60s, 재시도 무한 |
| SSE 메시지 파싱 실패 | `logger.warning(...)` 후 다음 메시지로 진행, decision 유실은 backfill 에서 회수 |
| DB UPSERT 실패 (connection) | pool 재획득, 실패 3 회 누적 시 `bridge._healthy=False` 전환, `/health` 에 반영 |
| DB UPSERT 성공했으나 summary UPSERT 실패 | 원본은 저장됨, summary 는 야간 rebuild 스크립트로 복구 |

---

## 7. Security Considerations

- [x] Bridge → Relay 호출에 `X-API-Key: ${IOT_RELAY_API_KEY}` 헤더 필수 (`.env`, 리포 미커밋)
- [x] FarmOS API 는 기존 세션 의존성(`Depends(get_current_user)`) 재사용. 미인증 시 401.
- [x] `action` / `tool_calls` / `sensor_snapshot` 은 JSONB 저장 전 타입 체크(Pydantic). Raw string 삽입 방지.
- [x] Detail Modal 의 `Copy` 는 `navigator.clipboard.writeText` 만 사용(직렬화 XSS 차단, DOM 삽입 없음).
- [x] CORS: 기존 FarmOS CORS 정책 유지, Relay 직접 호출은 FE 에서 제거.
- [x] Rate Limit: `/decisions` `limit` 최대 100 하드 캡, `offset`/cursor 검증.
- [x] PII 없음: decision 은 환경 제어 로직만 담음. user_id 저장 없음.

---

## 8. Test Plan (v2.3.0)

### 8.1 Test Scope

| Type | Target | Tool | Phase | 최종 결과 (2026-04-20) |
|------|--------|------|-------|------------------------|
| L1: API | 5개 endpoint + auth + validation | curl + cookie | Check | ✅ **26/26 PASS** |
| L1: Bridge Unit | parse, upsert, backfill 함수 | pytest (mock httpx) | — | ⏸ 스킵 (Dynamic level 범위 외) |
| L2: UI Action | SummaryCards 탭 / 더보기 / row click | Playwright | Check | ✅ **6/6 PASS (U1-U6)** |
| L3: E2E | 대시보드 로드 → 요약·목록 → 더보기 → 상세 | Playwright | Check | ⚠️ **2/3 PASS (E1 ✅, E3 ✅, E2 미구현)** |

### 8.2 L1 API Scenarios

| # | Endpoint | Method | Test | Expected |
|---|----------|--------|------|----------|
| 1 | /ai-agent/activity/summary?range=today | GET | 빈 DB | 200, total=0, by_* = {} |
| 2 | /ai-agent/activity/summary?range=7d | GET | seed 3건 (서로 다른 day) | 200, total=3, by_control_type 키 3개 |
| 3 | /ai-agent/activity/summary?range=bogus | GET | invalid | 400, code=INVALID_RANGE |
| 4 | /ai-agent/decisions?limit=20 | GET | seed 25건 | 200, items.length=20, next_cursor 존재, has_more=true |
| 5 | /ai-agent/decisions?cursor=<N-1 created_at>&limit=20 | GET | follow-up | 200, items.length=5, has_more=false |
| 6 | /ai-agent/decisions?control_type=ventilation | GET | seed 혼합 | 200, 모든 item.control_type === "ventilation" |
| 7 | /ai-agent/decisions/{id} | GET | 존재 id | 200, shape 전체 필드 |
| 8 | /ai-agent/decisions/{bogus} | GET | 없는 id | 404, code=DECISION_NOT_FOUND |
| 9 | /ai-agent/* | GET | no auth | 401 |

### 8.3 L1 Bridge Unit Scenarios

| # | Target | Test | Expected |
|---|--------|------|----------|
| B1 | `_parse_sse_line` | `event: ai_decision\ndata: {..}` | dict 반환 |
| B2 | `upsert_decision` | 동일 id 2번 | 두번째는 no-op (count 1) |
| B3 | `bump_summary_daily` | 같은 (day, ctype) 2번 | count=2, by_source 합산 |
| B4 | `backfill_since` | mock /decisions 2 페이지 | 전부 upsert, 로그에 count 기록 |
| B5 | `connect` | httpx 예외 → 재시도 | backoff 호출, 최종 성공 시 상태 healthy |

### 8.4 L2 UI Action Scenarios

| # | Page | Action | Result |
|---|------|--------|--------|
| U1 | Dashboard | 로드 | SummaryCards §5.4 전 요소 표시 |
| U2 | Dashboard | 탭 `7일` 클릭 | `/activity/summary?range=7d` 호출 확인 (request interception) |
| U3 | Dashboard | 더보기 클릭 | `/decisions?cursor=…` 호출 확인, 목록 20→40 |
| U4 | Dashboard | row 클릭 | DetailModal 열림, §5.4 모달 요소 전부 표시 |
| U5 | Dashboard | DetailModal Copy | clipboard 에 action JSON 존재 |
| U6 | Dashboard | Esc | DetailModal close + focus 원복 |

### 8.5 L3 E2E Scenarios

| # | Scenario | Steps | Success | 결과 |
|---|----------|-------|---------|:--:|
| E1 | Load→Summary→List→More→Detail | Dashboard → `오늘` 숫자 확인 → 목록 20 → 더보기 → 40 → row → 모달 오픈 → Copy Action → Esc → 닫힘 | 모든 단계 에러 없음, Network 401/500 없음 | ✅ PASS (1.8s) |
| E2 | SSE 실시간 | 테스트 도중 mock Relay 가 `ai_decision` push → 목록 최상단 prepend + `오늘` total +1 | 5 초 내 반영 | ⏸ **미구현** (EventSource mock 복잡 or 실 Relay 연동 필요) |
| E3 | Bridge 장애 (mock 빈 응답) | `/decisions` mock → items=[], `/activity/summary` mock → total=0 → 목록 빈 상태 정상 렌더 | 더보기 버튼 미표시, `총 판단 0건` 확인 | ✅ PASS (2.2s) |

### 8.6 Seed Data Requirements

| Entity | Minimum Count | Key Fields |
|--------|:-:|------|
| ai_agent_decisions | 30 | 서로 다른 `timestamp` (오늘 20, 어제 10), 3 종 `control_type`, 3 종 `source` |
| ai_agent_activity_daily | 3 | today, yesterday, 3 일 전 |
| ai_agent_activity_hourly | 6 | 최근 6 시간 |

`backend/scripts/seed_ai_agent.py` 를 Do 단계에서 작성.

---

## 9. Clean Architecture

### 9.1 Layer Structure (FastAPI 기준)

| Layer | Responsibility | Location |
|-------|---------------|----------|
| **Presentation** | HTTP 라우팅, Pydantic in/out | `backend/app/api/ai_agent.py`, FE 컴포넌트 |
| **Application** | Bridge Worker(sse/backfill/summarize), 조회 유스케이스 | `backend/app/services/ai_agent_bridge.py` |
| **Domain** | 엔티티 타입, decision→summary 집계 규칙 | `backend/app/schemas/ai_agent.py` + 타입 |
| **Infrastructure** | DB 쿼리, httpx 클라이언트 | SQLAlchemy 모델(`models/ai_agent.py`), httpx.AsyncClient |

### 9.2 Dependency Rules

```
FE Component ──▶ useAIAgent(hook) ──▶ fetch() ──▶ API Router ──▶ Service/Bridge ──▶ Model/DB
                                                  └──────────────▶ httpx ──▶ Relay
```

- Service 는 Model 을 import, API 는 Service + Schema 를 import. 역방향 금지.
- FE 컴포넌트는 직접 fetch 하지 않고 훅을 경유.

### 9.3 This Feature's Layer Assignment

| Component | Layer | Location |
|-----------|-------|----------|
| `AiAgentDecision`, `AiAgentActivityDaily`, `AiAgentActivityHourly` | Infrastructure (ORM) | `backend/app/models/ai_agent.py` |
| `DecisionOut`, `SummaryOut`, `DecisionListOut` | Domain/Schema | `backend/app/schemas/ai_agent.py` |
| `AiAgentBridge` 클래스 + 함수 | Application | `backend/app/services/ai_agent_bridge.py` |
| `router` (GET summary/list/detail) | Presentation | `backend/app/api/ai_agent.py` |
| `AIAgentPanel`, `AIActivitySummaryCards`, `AIDecisionDetailModal` | Presentation | `frontend/src/modules/iot/` |
| `useAIAgent` | Application(FE) | `frontend/src/hooks/useAIAgent.ts` |

---

## 10. Coding Convention Reference

### 10.1 Naming

| Target | Rule | Example |
|--------|------|---------|
| Python module | snake_case | `ai_agent_bridge.py` |
| Python class | PascalCase | `AiAgentDecision` |
| SQL table | snake_case | `ai_agent_decisions` |
| TS component | PascalCase | `AIDecisionDetailModal` |
| TS hook | camelCase (use*) | `useAIAgent` |

### 10.2 Environment Variables

| Var | Scope | Default | Note |
|-----|-------|---------|------|
| `IOT_RELAY_BASE_URL` | BE | `http://localhost:9000` | Relay 기본 URL |
| `IOT_RELAY_API_KEY` | BE | (required) | X-API-Key 헤더 |
| `AI_AGENT_BRIDGE_ENABLED` | BE | `false` | Worker on/off |
| `AI_AGENT_MIRROR_TTL_DAYS` | BE | `30` | TTL |
| `AI_AGENT_BACKFILL_PAGE_SIZE` | BE | `200` | 기동 backfill 페이지 |
| `VITE_API_BASE` | FE | `/api/v1` | 기존 재사용 확인 |

### 10.3 This Feature's Conventions

| Item | Convention |
|------|-----------|
| Component naming | `AI` 접두 유지 (기존 `AIAgentPanel` 일관) |
| File organization | 신규 FE 컴포넌트는 `modules/iot/` 평면 배치 (서브 디렉터리 미생성) |
| State management | 훅 `useAIAgent` 단일 소유, Context/Zustand 미사용 |
| Error handling | 훅 내부 try/catch → 상태 `error` 필드로 노출, 모달은 에러 시 닫힘 + toast |

---

## 11. Implementation Guide

### 11.1 File Structure

```
backend/app/
├── models/
│   └── ai_agent.py                ★ NEW
├── schemas/
│   └── ai_agent.py                ★ NEW
├── services/
│   └── ai_agent_bridge.py         ★ NEW
├── api/
│   └── ai_agent.py                ★ NEW
├── core/
│   └── config.py                  ✏ MODIFY (env 추가)
└── main.py                        ✏ MODIFY (router 등록 + lifespan bridge task)

backend/scripts/
└── seed_ai_agent.py               ★ NEW (테스트 seed)

backend/tests/
├── test_ai_agent_api.py           ★ NEW (L1 API)
└── test_ai_agent_bridge.py        ★ NEW (L1 Bridge unit)

frontend/src/
├── hooks/
│   └── useAIAgent.ts              ✏ MODIFY
├── types/
│   └── index.ts                   ✏ MODIFY (AIDecision 확장)
└── modules/iot/
    ├── AIAgentPanel.tsx           ✏ MODIFY
    ├── AIActivitySummaryCards.tsx ★ NEW
    └── AIDecisionDetailModal.tsx  ★ NEW

frontend/tests/e2e/
└── agent-action-history.spec.ts   ★ NEW (L2 + L3)

docs/
├── backend-architecture.md        ✏ MODIFY (Bridge 섹션)
├── database-schema.md             ✏ MODIFY (3 테이블)
└── iot-relay-server-postgres-patch.md  ✏ MODIFY (§10 신규)
```

### 11.2 Implementation Order

1. [ ] **Module 1**: Backend 모델/스키마 + DDL 적용
2. [ ] **Module 2**: Backend API (`/summary`, `/decisions`, `/decisions/{id}`) — seed 기반 동작
3. [ ] **Module 3**: Bridge Worker + lifespan 통합 + backfill
4. [ ] **Module 4**: Frontend 훅/타입 확장 + SummaryCards + DetailModal + Panel 통합
5. [ ] **Module 5**: Relay patch-spec 문서(§10 iot_agent_decisions 섹션) 및 docs 갱신
6. [ ] **Module 6**: 테스트(L1 + L2 + L3) + seed 스크립트

### 11.3 Session Guide

> Use `/pdca do agent-action-history --scope module-N`

#### Module Map

| Module | Scope Key | Description | Estimated Turns |
|--------|-----------|-------------|:---------------:|
| BE Schema/Model | `module-1` | `models/ai_agent.py`, `schemas/ai_agent.py`, `core/config.py` env 추가, `main.py` 모델 import | 15-20 |
| BE API | `module-2` | `api/ai_agent.py` 3 endpoints + `seed_ai_agent.py` + L1 API 테스트 | 20-25 |
| BE Bridge | `module-3` | `services/ai_agent_bridge.py` + `main.py` lifespan + L1 Bridge unit 테스트 | 25-30 |
| FE Components | `module-4` | `useAIAgent` 확장, `AIActivitySummaryCards`, `AIDecisionDetailModal`, `AIAgentPanel` 수정, 타입 확장 | 25-30 |
| Docs + Relay Patch Spec | `module-5` | `docs/iot-relay-server-postgres-patch.md` §10, `docs/database-schema.md`, `docs/backend-architecture.md` | 10-15 |
| E2E Tests | `module-6` | Playwright L2/L3 시나리오 `agent-action-history.spec.ts` | 15-20 |

#### Recommended Session Plan

| Session | Phase | Scope | Turns |
|---------|-------|-------|:-----:|
| S1 (완료) | Plan + Design | 전체 | 30-35 |
| S2 | Do | `--scope module-1,module-2` | 35-45 |
| S3 | Do | `--scope module-3` | 25-30 |
| S4 | Do | `--scope module-4` | 25-30 |
| S5 | Do | `--scope module-5,module-6` | 25-35 |
| S6 | Check + Report | 전체 | 30-40 |

#### Module 간 의존성

```
module-1 ──▶ module-2 ──▶ module-3
                            │
                            └──▶ module-4 ──▶ module-6
                            │
                            └──▶ module-5 (병렬 가능)
```

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-20 | Initial draft — Option C 선택, DDL/API/컴포넌트 확정, Module Map 6개 | clover0309 |
| 0.2 | 2026-04-20 | §8 Test Plan 에 최종 실행 결과 추가 (L1 26/26, L2 6/6, L3 2/3) + E2 미구현 명시 | clover0309 |
| 0.3 | 2026-04-23 | Code Sync — Status 를 Production 으로 상향. 구현체 파일 경로(§11.1) 는 코드와 1:1 매치 확인됨: `backend/app/services/ai_agent_bridge.py`, `backend/app/api/ai_agent.py`, `backend/app/models/ai_agent.py`, `frontend/src/modules/iot/AI*Panel.tsx` / `AIActivitySummaryCards.tsx` / `AIDecisionDetailModal.tsx`, `frontend/src/hooks/useAIAgent.ts`. 피처 플래그 `AI_AGENT_BRIDGE_ENABLED` 배포 절차는 `docs/backend-architecture.md §AI Agent Bridge Worker` 참조. SSE broadcast 불변식(persist → broadcast) 은 `docs/iot-ai-agent-implementation.md §13.2` 로 이관. | clover0309 |
