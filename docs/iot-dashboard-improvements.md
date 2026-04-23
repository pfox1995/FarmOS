# IoT 대시보드 개선 작업 정리

> 작성일: 2026-04-07

---

## 1. 관수 이력 / 센서 알림 더보기 기능

### 배경
관수 이력과 센서 알림이 페이징 없이 전체 목록을 표시하고 있어, 데이터가 많아지면 화면이 길어지는 문제가 있었다.

### 변경 내용
- **관수 이력**: 초기 3건 표시, "더보기" 클릭 시 모달로 전체 이력 + 그래프 시각화
- **센서 알림**: 초기 3건 표시, "더보기" 클릭 시 3건씩 추가 로드, "접기"로 복귀

### 수정 파일
- `frontend/src/modules/iot/IoTDashboardPage.tsx`

---

## 2. 관수 이력 모달 + 그래프 시각화

### 배경
관수 이력을 리스트로만 보는 것보다 시각적으로 한눈에 파악할 수 있도록 그래프가 필요했다.

### 변경 내용
- "더보기" 버튼 클릭 시 모달 오픈
- 모달 구성:
  - 상단: "관수 이력 상세" 제목 + 닫기(X) 버튼
  - 중단: Recharts BarChart (X축: 날짜/시간, 바 높이: 관수 시간(분), 색상: 밸브 열림/닫힘)
  - 하단: 전체 관수 이력 스크롤 리스트 (자동/수동 관수 구분 표시)
- ESC 키 / 배경 클릭으로 닫기, 모달 열린 동안 배경 스크롤 방지

### IrrigationModal 컴포넌트 (IoTDashboardPage.tsx 내부)
- `BarChart` + `Cell`로 밸브 상태별 색상 분기 (열림: `#3B82F6`, 닫힘: `#9CA3AF`)
- `useEffect`로 ESC 키 리스너, body overflow 제어

### 수정 파일
- `frontend/src/modules/iot/IoTDashboardPage.tsx`

---

## 3. 토양 습도 추정 로직 (mock 개선)

### 배경
토양 습도 센서를 보유하지 않아 `random.uniform(20, 90)`으로 랜덤 생성하고 있었다.
실제 센서값(온도, 대기 습도, 조도)과 무관하게 20~90% 사이를 뛰어다녀 비현실적인 데이터가 표시되었다.

### 설계 원리

| 요소 | 물리적 근거 | 적용 방식 |
|------|------------|----------|
| 토양 기본 보유 수분 | 토양은 수분을 오래 보유함 | 기본값 55% |
| 대기 습도 | 높으면 증발 억제, 강우 가능성 | 50% 기준 ±0.3%p per 1% |
| 온도 | 높으면 증발량 증가 | 20℃ 기준, 1℃당 -0.4% |
| 조도 | 높으면 일사량 증가, 증발 촉진 | (조도/100) × 2 감소 |
| 시간 관성 | 토양 습도는 급변하지 않음 | 이전값 70% + 새값 30% 블렌딩 |
| 노이즈 | 자연스러운 변동 | ±2% |
| 범위 제한 | 비현실적 값 방지 | 20% ~ 85% 클램프 |

### 계산 공식
```
estimated = 55 + (humidity - 50) × 0.3 - (temperature - 20) × 0.4 - (light / 100) × 2 ± noise
final = prev × 0.7 + estimated × 0.3  (시간 관성)
clamp(20, 85)
```

### 검증 예시

| 조건 | 온도 | 대기습도 | 조도 | 추정 토양습도 |
|------|------|---------|------|-------------|
| 한낮 맑음 | 30℃ | 45% | 80% | ~28% |
| 실내 건조 | 24℃ | 26.5% | 12% | ~46% |
| 흐린 오후 | 22℃ | 70% | 20% | ~53% |
| 비 오는 날 | 18℃ | 92% | 5% | ~72% |

### 수정 파일
- `iot_relay_server/app/store.py` — 실제 서비스 (iot.lilpa.moe)
- `backend/app/core/store.py` — 로컬 개발용 (동기화)

### 주의사항
- 프론트엔드가 호출하는 서버는 `iot_relay_server/`이므로, 토양 습도 로직 변경 시 이 쪽을 반드시 수정해야 함
- `backend/`는 로컬 개발 환경용이므로 함께 동기화 권장

---

## 4. 연결 끊김 판정 개선 (5회 연속 실패)

### 배경
프론트엔드에서 백엔드 API 호출이 1회라도 실패하면 즉시 "백엔드 연결 안 됨"으로 표시되었다.
일시적인 네트워크 지연에도 연결 상태가 깜빡이는 문제가 있었다.

### 변경 내용
- `useRef`로 연속 실패 횟수(`failCount`) 추적
- **연속 5회 실패** 시에만 `connected: false`로 전환
- 성공 1회로 즉시 `failCount` 초기화 + `connected: true` 복구
- 30초 폴링 기준 약 **2분 30초** 동안 응답 없을 때 끊김 판정

### 수정 파일
- `frontend/src/hooks/useSensorData.ts`

---

## 5. AI Agent Panel + SSE 이벤트 소비 (2026-04-23 추가)

<!-- Code Sync: 2026-04-23 -->

2026-04-07 이후 IoT 대시보드는 센서 표시 기능을 넘어, AI Agent 판단 이력·요약·상세 모달과 수동 제어 패널까지 통합된 상태다. 아래는 현재 production 코드(2026-04-23 기준) 의 프론트엔드 구조다.

### 5.1 컴포넌트 트리 (IoTDashboardPage)

```
IoTDashboardPage.tsx
├── SensorCards            (기존)
├── IrrigationHistoryList + IrrigationModal (기존 §1~2)
├── SensorAlertList        (기존 §1)
├── ManualControlPanel     (iot-manual-control feature)
│   ├── ControlCard × 4    (환기/관수/조명/차광)
│   └── SimulationBar      (시뮬레이션 모드)
└── AIAgentPanel           (Tool Calling 전환 후)
    ├── AIActivitySummaryCards   (오늘/7일/30일 탭 집계)
    ├── 4대 제어 상태 카드
    ├── 최근 판단 목록            (row 클릭 → DetailModal)
    └── AIDecisionDetailModal    (tool_calls, sensor_snapshot 표시)
```

### 5.2 SSE 단일 연결, 다중 이벤트 소비

`useSensorData.ts` 는 단일 EventSource(`/api/v1/sensors/stream`) 를 유지하며, 이벤트 타입별로 별도 핸들러 레지스트리를 두고 여러 훅/컴포넌트가 중복 연결 없이 구독한다.

| 이벤트 | 핸들러 레지스트리 | 소비 훅/컴포넌트 |
|--------|------------------|------------------|
| `sensor` | 내부 state 업데이트 | SensorCards |
| `alert` | 내부 state 업데이트 | SensorAlertList |
| `irrigation` | 내부 state 업데이트 | IrrigationHistoryList |
| `control` | `_controlHandlers` | `useManualControl.handleControlEvent` → ManualControlPanel |
| `ai_decision` | `_aiDecisionHandlers` | `useAIAgent` → AIAgentPanel (prepend + 요약 숫자 증가) |

실패 감지는 기존 5회 연속 실패 규칙(§4)을 유지하며, EventSource 는 자동 재연결.

### 5.3 useAIAgent 2-base 패턴

`useAIAgent` 는 두 개의 API base 를 동시에 사용한다.

| Base | 용도 | 호출 대상 |
|------|------|----------|
| Relay `VITE_IOT_API_URL` (예: `http://iot.lilpa.moe:9000/api/v1`) | Agent ON/OFF, 작물 프로필, 수동 오버라이드 | `/ai-agent/toggle`, `/ai-agent/crop-profile`, `/ai-agent/override` |
| FarmOS `VITE_API_BASE` (예: `/api/v1`) | 판단 이력 조회 (미러) + 요약 | `/ai-agent/activity/summary`, `/ai-agent/decisions?cursor=...`, `/ai-agent/decisions/{id}` |

이력 조회를 FarmOS BE 로 돌리는 이유는 FarmOS Bridge Worker 가 최근 30일 미러 + 집계 테이블을 들고 있어 Relay 재시작과 무관하게 이력이 유지되기 때문이다. `ai_agent_decisions` row 의 `id` 는 Relay UUID 를 그대로 PK 로 재사용하므로 Detail Modal 의 "원본 id" 도 동일하다.

### 5.4 SSE `ai_decision` 소비 규칙

- 수신 payload 는 `AIDecision` 전체 shape (id/reason/action/tool_calls/sensor_snapshot/duration_ms).
- **persist → broadcast** 순서가 Relay 측에서 보장되므로 (`iot-ai-agent-implementation.md §13.2`), FE 는 FarmOS Bridge 의 eventual consistency 에 의존할 필요 없이 payload 를 그대로 prepend 할 수 있다.
- 요약 카드는 현재 탭이 `today` 일 때만 증분 계산(total + by_*) 한다. 다른 탭은 탭 전환 시 `/activity/summary?range=...` 를 재조회한다.

### 5.5 수정 / 신규 파일 (2026-04-16 ~ 2026-04-20)

| 파일 | 상태 | 책임 |
|------|:----:|------|
| `frontend/src/modules/iot/AIAgentPanel.tsx` | ✏ MODIFY | row 전체 클릭 → DetailModal, 기존 "도구 호출 N건" 버튼 제거 |
| `frontend/src/modules/iot/AIActivitySummaryCards.tsx` | ★ NEW | 오늘/7일/30일 탭 + 4카드 (total / top1 ctype / top1 source / avg duration) |
| `frontend/src/modules/iot/AIDecisionDetailModal.tsx` | ★ NEW | reason / action / sensor_snapshot / tool_calls (N) 렌더 + Copy 버튼 |
| `frontend/src/modules/iot/ManualControlPanel.tsx` | ★ NEW | 4종 제어 카드 + 시뮬레이션 모드 토글 |
| `frontend/src/hooks/useAIAgent.ts` | ✏ MODIFY | 2-base 패턴 + `fetchMore(cursor)` `fetchDetail(id)` `fetchSummary(range)` + SSE prepend |
| `frontend/src/hooks/useManualControl.ts` | ★ NEW | 제어 상태 관리 + SSE control 이벤트 수신 + 시뮬레이션 버튼 |
| `frontend/src/hooks/useSensorData.ts` | ✏ MODIFY | `addEventListener('control')`, `addEventListener('ai_decision')` + 핸들러 레지스트리 |
| `frontend/src/types/index.ts` | ✏ MODIFY | `AIDecision` id 필수화, `sensor_snapshot?`·`duration_ms?`·`created_at?` 추가, `ControlEvent`/`ManualControlState` 등 |

---

## 수정 파일 전체 목록

| 파일 | 변경 항목 |
|------|----------|
| `frontend/src/modules/iot/IoTDashboardPage.tsx` | 더보기, 모달+그래프, ManualControlPanel 통합 |
| `frontend/src/hooks/useSensorData.ts` | 5회 연속 실패 연결 끊김 + control/ai_decision SSE 핸들러 |
| `frontend/src/modules/iot/AIAgentPanel.tsx` | row 클릭 상세 모달, 요약 카드 슬롯 |
| `frontend/src/modules/iot/AIActivitySummaryCards.tsx` | **신규** — 오늘/7일/30일 탭 요약 |
| `frontend/src/modules/iot/AIDecisionDetailModal.tsx` | **신규** — tool_calls trace 상세 |
| `frontend/src/modules/iot/ManualControlPanel.tsx` | **신규** — 수동 제어 UI + 시뮬레이션 |
| `frontend/src/hooks/useAIAgent.ts` | 2-base 패턴 + pagination + SSE prepend |
| `frontend/src/hooks/useManualControl.ts` | **신규** — 제어 상태 + SSE control 수신 |
| `iot_relay_server/app/store.py` | 토양 습도 추정 로직 (서비스) + `add_agent_decision` · `list_agent_decisions` |
| `iot_relay_server/app/control_store.py` | **신규** — 제어 상태 인메모리 + 파일 영속화 |
| `iot_relay_server/app/control_routes.py` | **신규** — 5개 제어 엔드포인트 |
| `iot_relay_server/app/tools/definitions.py` | **신규** — 8개 Tool JSON Schema |
| `iot_relay_server/app/tools/executor.py` | **신규** — Tool 실행 디스패처 |
| `backend/app/services/ai_agent_bridge.py` | **신규** — SSE + backfill + 멱등 UPSERT + daily/hourly |
| `backend/app/api/ai_agent.py` | **신규** — 미러 읽기 API (JWT 인증) |
| `backend/app/models/ai_agent.py` | **신규** — 3 테이블 ORM |
| `backend/app/core/store.py` | 토양 습도 추정 로직 (로컬 동기화) |
