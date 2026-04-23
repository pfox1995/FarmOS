# IoT AI Agent — Tool Calling 전환 브리핑 보고서

> **작성일**: 2026-04-14
> **브랜치**: refact/iotdashboard
> **상태**: Phase 1~5 구현 + 테스트 완료

---

## 1. 프로젝트 개요

기존 IoT AI Agent의 아키텍처를 **REST API JSON 생성 패턴 → OpenAI Function Calling (Tool Use) 패턴**으로 전환.
AI Agent(gpt-5-mini)가 센서/기상/제어 장치를 **도구(Tool)로 자율 호출**하여 스마트팜 온실을 자동 제어한다.

### 변경 전 vs 변경 후

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| LLM 역할 | JSON 생성 → 파싱 → 적용 | **Tool 자율 호출 → 직접 실행** |
| LLM 모델 | gpt-5-nano (존재하지 않는 모델) | **gpt-5-mini** (OpenRouter) |
| 판단 구조 | 규칙 + LLM JSON 출력 | **규칙(긴급) + LLM Tool Calling(미세조정)** |
| Tool 정의 | 없음 | **8개 Tool** (읽기 4 + 제어 4) |
| 판단 추적 | reason 텍스트만 | **tool_calls trace** (호출 이력 전체 기록) |

---

## 2. 아키텍처

```
ESP8266 (DHT11 + CdS, 30초 간격)
    │ HTTP POST
    v
릴레이 서버 (N100, Docker)
    ├─ store.py: 센서 저장 + 토양습도 가상 추정
    ├─ sensor_filter.py: 센서 이상값 필터링
    ├─ weather_client.py: 기상청 API (또는 mock)
    ├─ ai_agent.py: 규칙 엔진(30초) + LLM Tool Calling(5분)
    ├─ tools/
    │   ├─ definitions.py: 8개 Tool JSON Schema 정의
    │   └─ executor.py: Tool 실행 디스패처
    └─ /api/v1/ai-agent/* 엔드포인트
          │ SSE + 30초 폴링
          v
    프론트엔드 대시보드 (AIAgentPanel)
        └─ tool-call trace 표시, SourceBadge "AI Tool"
```

### 2레이어 판단 구조

```
센서 데이터 수신 (30초마다)
    │
    ├─ [Layer 1] 규칙 엔진 (즉시, 매 호출)
    │   - 긴급: 온도>35C → 환기 100%
    │   - 긴급: 토양수분<30% → 즉시 관수
    │   - 긴급: 야간 외부<5C → 보온커튼 100%
    │   - 일반: 저조도 보광, 고조도 차광, 정상복귀 등
    │
    └─ [Layer 2] LLM Tool Calling (5분 간격, 유의미 변화 시)
        1. 프롬프트에 센서/기상/작물/제어 데이터 포함
        2. LLM이 read_* tool로 추가 정보 조회 (선택)
        3. LLM이 control_* tool 자율 호출 (미세 조정)
        4. 판단 근거(reason)와 tool_calls trace 기록
```

---

## 3. Tool 목록 (8개)

### 읽기 Tool (4개)
| Tool | 설명 |
|------|------|
| `read_sensors` | 온실 내부 센서값 (온도, 습도, 조도, 토양수분) |
| `read_weather` | 외부 기상 실황 + 3/6/12시간 예보 |
| `read_crop_profile` | 재배 작물 적정 환경 조건 |
| `read_control_state` | 현재 제어 장치 상태 |

### 제어 Tool (4개)
| Tool | 파라미터 | 설명 |
|------|----------|------|
| `control_ventilation` | window_open_pct(0~100), fan_speed(0~3000), reason | 환기 |
| `control_irrigation` | valve_open, water_amount_L(0~20), nutrient_N/P/K, reason | 관수/양액 |
| `control_lighting` | on, brightness_pct(0~100), reason | 보광등 |
| `control_shading` | shade_pct(0~100), insulation_pct(0~100), reason | 차광/보온 |

---

## 4. 변경된 파일

### 삭제 (Phase 0: 중복 코드 클린업)
| 파일 | 사유 |
|------|------|
| `backend/app/core/ai_agent.py` | relay server와 중복 |
| `backend/app/core/ai_agent_prompts.py` | 중복 |
| `backend/app/api/ai_agent.py` | frontend가 relay server 직접 호출 |

### 신규 생성
| 파일 | 설명 |
|------|------|
| `iot_relay_server/app/tools/__init__.py` | 패키지 |
| `iot_relay_server/app/tools/definitions.py` | 8개 Tool JSON Schema 정의 |
| `iot_relay_server/app/tools/executor.py` | Tool 실행 디스패처 + 핸들러 |

### 재작성
| 파일 | 변경 내용 |
|------|-----------|
| `iot_relay_server/app/ai_agent.py` | LLM JSON → Tool Calling 루프, 규칙 엔진 정리 |
| `iot_relay_server/app/ai_agent_prompts.py` | Tool Use 시스템 프롬프트 + 제어 판단 가이드 |

### 버그 수정
| 파일 | 수정 내용 |
|------|-----------|
| `iot_relay_server/app/config.py` | gpt-5-nano → gpt-5-mini |
| `iot_relay_server/app/store.py` | 토양수분 light_effect 스케일 수정 (100→100,000 기준) |
| `iot_relay_server/app/weather_client.py` | KMA 실황 시 빈 forecast → mock 예보 보충 |
| `iot_relay_server/app/sensor_filter.py` | light 센서 장기 0값 감쇠 처리 |
| `iot_relay_server/app/main.py` | test-trigger 파라미터 + 디버그 정보 추가 |
| `backend/app/core/config.py` | gpt-5-nano → gpt-5-mini |
| `backend/app/main.py` | ai_agent 라우터 제거 |
| `backend/app/core/store.py` | ai_agent 호출부 제거 |

### 프론트엔드
| 파일 | 변경 내용 |
|------|-----------|
| `frontend/src/types/index.ts` | `ToolCallTrace` 타입 추가, source에 "tool" 추가 |
| `frontend/src/modules/iot/AIAgentPanel.tsx` | "AI Tool" 뱃지 + tool-call trace 펼쳐보기 UI |

---

## 5. 테스트 결과

### Phase 2: 환기 제어
| 시나리오 | 결과 |
|----------|------|
| 규칙: 온도 36.5C → 긴급 환기 | ✅ 창문 100%, 팬 3000 RPM |
| 규칙: 온도 32C → 자연환기 | ✅ 창문 80%, 팬 1500 RPM |
| LLM: 온도 32C → 미세조정 | ✅ 창문 85%, 팬 1800 RPM (외부 23C 감안) |
| 정상 복귀 → 환기 해제 | ✅ |

### Phase 3: 관수/양액
| 시나리오 | 결과 |
|----------|------|
| 규칙: 토양수분 25% → 긴급 관수 | ✅ 3L 관수 |
| LLM: 토양수분 35% → 자율 관수 | ✅ 5L, N=1.5/P=0.8/K=2.0 (개화기 칼륨 강화) |

### Phase 4: 조명
| 시나리오 | 결과 |
|----------|------|
| 규칙: 조도 2000 lux → 보광등 | ✅ 60% |
| LLM: 조도 8000 lux → 미세조정 | ✅ 70% (규칙 미발동 구간에서 LLM 자율 판단) |

### Phase 5: 차광/보온
| 시나리오 | 결과 |
|----------|------|
| LLM: 외부 8C + 야간 → 보온 | ✅ 보온커튼 100% (예보 3.2~5.4C 감안) |
| LLM: 동시에 보광등 100% | ✅ 열원 효과 판단하여 60%→100% 상향 |

---

## 6. 하드웨어 제약사항

| 센서/장치 | 상태 |
|-----------|------|
| ESP8266 | 정상 통신 (HTTP POST, 30초 간격) |
| DHT11 (온도/습도) | 실측 |
| KY-018 LDR (조도) | 실측 |
| 토양수분 | **가상 계산** (온도/습도/조도 기반 추정) |
| 제어 장치 (환기팬, 밸브 등) | **가상 시뮬레이션** (실 하드웨어 없음) |

---

## 7. 기술 스택

| 구분 | 기술 |
|------|------|
| AI Agent LLM | gpt-5-mini (OpenRouter 경유) |
| Tool Use 방식 | OpenAI Function Calling (tools 파라미터) |
| 백엔드 | FastAPI + httpx |
| 프론트엔드 | React + TypeScript |
| 배포 | Docker (N100 서버) |
| 기상 API | 기상청 초단기실황 + mock 예보 |

---

## 8. 향후 계획 / 후속 작업 결과

<!-- Code Sync: 2026-04-23 -->

### 8.1 완료 (2026-04-23 기준 production)

| 항목 | 완료 시점 | 결과 / 관련 문서 |
|------|-----------|-----------------|
| **제어 이력 PostgreSQL 영속화** | 2026-04-20 | Relay `iot_agent_decisions` 테이블 + `add_agent_decision()` · `list_agent_decisions()` · `get_agent_decision()` (`iot_relay_server/app/store.py`, DDL: `iot-relay-server-postgres-patch.md §10.1`). FarmOS 는 30일 미러(`ai_agent_decisions`) + 일/시간 요약 유지. |
| **FarmOS 연동 (SSE Bridge)** | 2026-04-20 | `backend/app/services/ai_agent_bridge.py` — SSE 상시 구독 + HTTP backfill + exponential backoff + 멱등 UPSERT. `AI_AGENT_BRIDGE_ENABLED` 플래그로 on/off. `agent-action-history` feature 로 별도 Design/Plan/Analysis/Report 보유. |
| **프론트엔드: 수동 제어 UI** | 2026-04-16 | `iot-manual-control` feature — `ManualControlPanel.tsx` + `useManualControl.ts` + `control_store.py` + `control_routes.py`. 시뮬레이션 모드(`POST /control/report` 직접 호출) 로 하드웨어 없이도 양방향 흐름 검증 가능. 상세는 `docs/02-design/features/iot-manual-control.design.md`. |
| **판단 이력 FE 모달** | 2026-04-20 | `AIDecisionDetailModal.tsx` + `AIActivitySummaryCards.tsx` + `useAIAgent` 확장 (2-base 패턴: Relay 토글 + FarmOS 결정 조회). cursor 기반 더보기, row 클릭 시 tool_calls·sensor_snapshot 표시. |

### 8.2 미완료 / 유보

| 항목 | 상태 | 사유 |
|------|:----:|------|
| LangChain 래핑 레이어 | ⏸ 보류 | 현재 OpenAI SDK 직접 호출로 충분. 팀 규모 확대 전까지 YAGNI. |
| 기상청 단기예보 API 연동 | ⏸ 보류 | KMA 초단기실황은 연동됨 (`weather_client.py`). 단기예보는 현재 mock 보충으로 판단 품질 저하 체감되면 재검토. |

### 8.3 후속 feature (별도 PDCA 사이클)

- `agent-action-history` (2026-04-20, 아카이브 완료) — 판단 영속화 + FE 상세 모달
- `iot-manual-control` (2026-04-16, 아카이브 완료) — 양방향 제어 + 시뮬레이션 모드
- `esp8266-led-sync` (2026-04-*, 아카이브 완료) — 하드웨어 LED 동기화
