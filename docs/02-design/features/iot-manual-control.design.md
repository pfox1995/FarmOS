# IoT Manual Control Design Document

> **Feature**: iot-manual-control
> **Architecture**: Option C — Pragmatic Balance
> **Plan Reference**: `docs/01-plan/features/iot-manual-control.plan.md`
> **Date**: 2026-04-16 (Code Sync: 2026-04-23)
> **Status**: **Production (Software-First 단계 완료)** — Relay `control_store.py` / `control_routes.py` / `main.py` 라우터 등록 + FE `ManualControlPanel.tsx` / `useManualControl.ts` / `useSensorData.ts` SSE control 이벤트 소비 구현 완료. ESP8266 펌웨어 폴링 루프 구현 완료 (`HARDWARE_BUTTONS_ENABLED=false` 상태로 빌드). 브레드보드 배선은 아직 미구성 — Phase 별 하드웨어 테스트(§8.2) 는 회로 구성 후 수행.
> **Archive**: `docs/archive/2026-04/manual-control-onoff/` (plan/design/analysis/report 완료 스냅샷)

---

## Context Anchor

| Key | Value |
|-----|-------|
| **WHY** | 센서 모니터링만 가능한 IoT 시스템에 실제 수동 제어 + 물리 버튼 제어를 추가하여 양방향 하드웨어 연동 달성 |
| **WHO** | FarmOS 사용자 (1인 농업인), 대시보드에서 원격 제어 + 현장에서 버튼 제어 |
| **RISK** | ESP8266 HTTP-only 통신 제약, 폴링 지연 (최대 수 초), Relay Server 코드 변경 시 N100 재배포 필요 |
| **SUCCESS** | 프론트엔드 토글 → 5초 내 ESP8266 LED 반응, ESP8266 버튼 → 2초 내 프론트엔드 반영 |
| **SCOPE** | Phase 1: 환기 → Phase 2: 관수/양액 → Phase 3: 조명 → Phase 4: 차광/보온 (순차, 테스트 후 진행) |

---

## 하드웨어 현황 (Critical Constraint)

> **현재 ESP8266에는 DHT11(D4) + KY-018 LDR(A0)만 연결되어 있습니다.**
> **버튼/LED 회로는 미구성 상태이며, 추후 브레드보드에서 구성 예정입니다.**

이 제약에 따른 설계 전략:

| 단계 | 설명 | 테스트 방식 |
|------|------|------------|
| **Step 1: Software-First** | Relay Server API + Frontend UI + 시뮬레이션 모드 구현 | 프론트엔드 시뮬레이션 모드로 양방향 흐름 검증 |
| **Step 2: ESP8266 펌웨어** | 폴링 루프 + 명령 수신 로직 추가 (LED/버튼 핀은 주석 처리) | curl로 `/control/commands` 폴링 시뮬레이션 |
| **Step 3: 하드웨어 배선** | 브레드보드에 버튼 + LED + 저항 연결 | 실물 양방향 테스트 |

**시뮬레이션 모드**: 프론트엔드 ManualControlPanel에 내장. ESP8266 없이도 프론트엔드가 직접 `/control/report`를 호출하여 "버튼 눌림" 이벤트를 발생시키고, SSE를 통해 UI가 반응하는 전체 흐름을 테스트할 수 있음.

---

## 1. Overview

### 1.1 선택된 아키텍처: Option C — Pragmatic Balance

- AI Agent와 수동 제어 **완전 분리** (별도 라우터, 별도 저장소, 별도 훅)
- 시뮬레이션 모드를 ManualControlPanel 내에 토글로 내장
- 신규 4파일 + 수정 4파일로 적정 규모
- Phase별 점진적 활성화 (환기 → 관수 → 조명 → 차광)

### 1.2 디렉토리 구조 (두 레포 걸침)

```
E:\new_my_study\himedia_FinalProject\
│
├── FarmOS\                                    ← Git repo (현재 작업 디렉토리)
│   ├── frontend\src\
│   │   ├── modules\iot\
│   │   │   ├── IoTDashboardPage.tsx           [수정] ManualControlPanel 임포트 추가
│   │   │   ├── AIAgentPanel.tsx               [유지] 변경 없음
│   │   │   └── ManualControlPanel.tsx         [신규] 수동 제어 UI + 시뮬레이션 모드
│   │   ├── hooks\
│   │   │   ├── useSensorData.ts               [수정] SSE control 이벤트 수신 추가
│   │   │   ├── useAIAgent.ts                  [유지] 변경 없음
│   │   │   └── useManualControl.ts            [신규] 제어 상태 관리 + API 호출
│   │   └── types\
│   │       └── index.ts                       [수정] ManualControlState 등 타입 추가
│   │
│   └── DH11_KY018_WiFi\
│       └── DH11_KY018_WiFi.ino               [수정] 폴링 루프 + 버튼/LED 로직 추가
│
└── iot_relay_server\                          ← 별도 디렉토리 (N100 Docker 배포)
    └── app\
        ├── main.py                            [수정] control_router 등록
        ├── store.py                           [유지] 변경 없음 (센서 전용)
        ├── schemas.py                         [수정] 제어 관련 스키마 추가
        ├── control_store.py                   [신규] 제어 상태 인메모리 저장 + 명령 큐
        └── control_routes.py                  [신규] 제어 API 5개 엔드포인트
```

---

## 2. Data Model

### 2.1 제어 상태 (Relay Server 인메모리)

```python
# iot_relay_server/app/control_store.py

from datetime import datetime, timezone

# 전체 제어 상태 — 서버 시작 시 파일에서 복원
control_state: dict = {
    "ventilation": {
        "active": False,        # 환기 작동 여부
        "window_open_pct": 0,   # 0~100
        "fan_speed": 0,         # 0~100 RPM
        "led_on": False,        # ESP8266 LED 상태
        "source": "manual",     # "manual" | "button" | "ai"
        "updated_at": None,     # ISO8601
    },
    "irrigation": {
        "active": False,
        "valve_open": False,
        "led_on": False,
        "source": "manual",
        "updated_at": None,
    },
    "lighting": {
        "active": False,
        "on": False,
        "brightness_pct": 0,    # 0~100
        "led_on": False,
        "source": "manual",
        "updated_at": None,
    },
    "shading": {
        "active": False,
        "shade_pct": 0,         # 0~100
        "insulation_pct": 0,    # 0~100
        "led_on": False,
        "source": "manual",
        "updated_at": None,
    },
}

# ESP8266이 폴링으로 가져갈 대기 명령 — 최신 상태 덮어쓰기 방식
pending_commands: dict = {}
# 예: {"ventilation": {"active": True, "window_open_pct": 70}, "timestamp": "..."}

# 제어 이력 (최근 100건)
control_history: list[dict] = []  # deque 대신 list + 슬라이싱
```

### 2.2 Frontend 타입 정의

```typescript
// frontend/src/types/index.ts 에 추가

// 개별 제어 항목 상태
export interface ControlItemState {
  active: boolean;
  led_on: boolean;
  source: "manual" | "button" | "ai";
  updated_at: string | null;
}

export interface VentilationState extends ControlItemState {
  window_open_pct: number;
  fan_speed: number;
}

export interface IrrigationControlState extends ControlItemState {
  valve_open: boolean;
}

export interface LightingState extends ControlItemState {
  on: boolean;
  brightness_pct: number;
}

export interface ShadingState extends ControlItemState {
  shade_pct: number;
  insulation_pct: number;
}

// 전체 수동 제어 상태
export interface ManualControlState {
  ventilation: VentilationState;
  irrigation: IrrigationControlState;
  lighting: LightingState;
  shading: ShadingState;
}

// 제어 명령 (프론트엔드 → Relay Server)
export interface ControlCommand {
  control_type: "ventilation" | "irrigation" | "lighting" | "shading";
  action: Record<string, unknown>;
  source: "manual" | "button";
}

// 제어 이벤트 (SSE로 수신)
export interface ControlEvent {
  control_type: string;
  state: Record<string, unknown>;
  source: string;
  timestamp: string;
}
```

### 2.3 Pydantic 스키마 (Relay Server)

```python
# iot_relay_server/app/schemas.py 에 추가

class ControlCommandIn(BaseModel):
    """프론트엔드 → 제어 명령"""
    control_type: str = Field(pattern=r"^(ventilation|irrigation|lighting|shading)$")
    action: dict
    source: str = Field(default="manual", pattern=r"^(manual|button|ai)$")

class ControlReportIn(BaseModel):
    """ESP8266 → 버튼/LED 상태 보고"""
    device_id: str
    control_type: str = Field(pattern=r"^(ventilation|irrigation|lighting|shading)$")
    state: dict
    source: str = Field(default="button")

class ControlAckIn(BaseModel):
    """ESP8266 → 명령 수신 확인"""
    device_id: str
    acknowledged_types: list[str]
```

---

## 3. API Design

### 3.1 Relay Server 신규 API (control_routes.py)

| # | Method | Path | Auth | Request | Response | 설명 |
|---|--------|------|------|---------|----------|------|
| 1 | `POST` | `/api/v1/control` | - | `ControlCommandIn` | `{ "status": "ok", "state": {...} }` | 프론트엔드 제어 명령 전송 |
| 2 | `GET` | `/api/v1/control/state` | - | - | `ManualControlState` 전체 | 현재 제어 상태 조회 |
| 3 | `GET` | `/api/v1/control/commands` | X-API-Key | `?device_id=esp8266-01` | `{ "commands": {...}, "timestamp": "..." }` | ESP8266 대기 명령 폴링 |
| 4 | `POST` | `/api/v1/control/report` | X-API-Key | `ControlReportIn` | `{ "status": "ok" }` | ESP8266 버튼/LED 상태 보고 |
| 5 | `POST` | `/api/v1/control/ack` | X-API-Key | `ControlAckIn` | `{ "status": "ok" }` | ESP8266 명령 수신 확인 (큐 클리어) |

### 3.2 API 상세 흐름

#### POST /api/v1/control (프론트엔드 → 제어 명령)

```python
# control_routes.py
@control_router.post("")
async def send_control(data: ControlCommandIn):
    # 1. control_state 업데이트
    update_control_state(data.control_type, data.action, data.source)
    # 2. pending_commands에 추가 (ESP8266이 폴링으로 가져감)
    add_pending_command(data.control_type, data.action)
    # 3. SSE broadcast (프론트엔드 즉시 반영)
    _broadcast("control", {
        "control_type": data.control_type,
        "state": control_state[data.control_type],
        "source": data.source,
        "timestamp": now_iso(),
    })
    return {"status": "ok", "state": control_state[data.control_type]}
```

#### GET /api/v1/control/commands (ESP8266 폴링)

```python
@control_router.get("/commands", dependencies=[Depends(verify_api_key)])
async def get_pending_commands(device_id: str = Query(...)):
    commands = get_and_clear_pending(device_id)
    # 명령이 없으면 빈 dict 반환
    return {"commands": commands, "timestamp": now_iso()}
```

**핵심**: ESP8266이 2~3초마다 이 엔드포인트를 호출. 새 명령이 있으면 가져가고, 없으면 빈 응답.

#### POST /api/v1/control/report (ESP8266 → 버튼 상태 보고)

```python
@control_router.post("/report", dependencies=[Depends(verify_api_key)])
async def report_control(data: ControlReportIn):
    # 1. control_state 업데이트 (source="button")
    update_control_state(data.control_type, data.state, data.source)
    # 2. SSE broadcast → 프론트엔드 즉시 반영
    _broadcast("control", {
        "control_type": data.control_type,
        "state": control_state[data.control_type],
        "source": "button",
        "timestamp": now_iso(),
    })
    return {"status": "ok"}
```

### 3.3 SSE 이벤트 확장

기존 store.py의 `_broadcast()` 함수를 control_store.py에서도 사용.
→ **store.py의 `_sse_subscribers` 리스트와 `_broadcast()` 함수를 공유**해야 함.

```python
# control_store.py에서 store.py의 broadcast를 import
from app.store import _broadcast
```

SSE 이벤트 포맷:

```
event: control
data: {
    "control_type": "ventilation",
    "state": {"active": true, "window_open_pct": 70, "led_on": true},
    "source": "manual",
    "timestamp": "2026-04-16T14:30:00Z"
}
```

---

## 4. Component Design

### 4.1 ManualControlPanel.tsx

```
┌─────────────────────────────────────────────────────────────────┐
│  수동 제어                                    [시뮬레이션 모드 🔘] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ 🌬️ 환기          │  │ 💧 관수/양액      │                     │
│  │                  │  │                  │                     │
│  │ [===●====] 70%   │  │ 밸브 [ON ● OFF]  │                     │
│  │ 창문 개폐율       │  │                  │                     │
│  │                  │  │ LED: 🟢          │                     │
│  │ LED: 🟢          │  │ 소스: 수동        │                     │
│  │ 소스: 수동        │  └──────────────────┘                     │
│  └──────────────────┘                                           │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ 💡 조명          │  │ 🛡️ 차광/보온      │                     │
│  │                  │  │                  │                     │
│  │ [ON ● OFF]       │  │ [===●====] 50%   │                     │
│  │ [===●====] 80%   │  │ 차광막            │                     │
│  │ 밝기             │  │ [===●====] 30%   │                     │
│  │                  │  │ 보온              │                     │
│  │ LED: ⚫          │  │                  │                     │
│  │ 소스: 버튼        │  │ LED: ⚫          │                     │
│  └──────────────────┘  │ 소스: -           │                     │
│                        └──────────────────┘                     │
│                                                                 │
│  ┌─ 시뮬레이션 모드 (하드웨어 미연결 시) ────────────────────────┐ │
│  │ [환기 버튼]  [관수 버튼]  [조명 버튼]  [차광 버튼]            │ │
│  │ ↑ 클릭하면 ESP8266 버튼 누름을 시뮬레이션                     │ │
│  │   (POST /control/report → SSE → UI 반영)                    │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 컴포넌트 구조

```
ManualControlPanel (메인 컨테이너)
├── ControlCard × 4 (환기/관수/조명/차광)
│   ├── 제어 UI (슬라이더/토글)
│   ├── LED 상태 인디케이터
│   └── 소스 배지 (수동/버튼/AI)
└── SimulationBar (시뮬레이션 모드 ON일 때 표시)
    └── SimButton × 4 (ESP8266 버튼 시뮬레이션)
```

### 4.3 useManualControl 훅

```typescript
// frontend/src/hooks/useManualControl.ts

const API_BASE = 'http://iot.lilpa.moe/api/v1';

export function useManualControl() {
  const [controlState, setControlState] = useState<ManualControlState | null>(null);
  const [simMode, setSimMode] = useState(false);

  // 초기 로드: GET /control/state
  useEffect(() => {
    fetchControlState();
  }, []);

  // 제어 명령 전송 (프론트엔드 → Relay)
  const sendCommand = async (
    controlType: ControlCommand['control_type'],
    action: Record<string, unknown>
  ) => { /* POST /api/v1/control */ };

  // 시뮬레이션: ESP8266 버튼 누름 흉내
  const simulateButton = async (
    controlType: ControlCommand['control_type']
  ) => { /* POST /api/v1/control/report (source: "button") */ };

  // SSE control 이벤트로 상태 업데이트 (useSensorData에서 콜백)
  const handleControlEvent = (event: ControlEvent) => {
    setControlState(prev => /* merge event into state */);
  };

  return {
    controlState,
    simMode,
    setSimMode,
    sendCommand,
    simulateButton,
    handleControlEvent,
  };
}
```

### 4.4 useSensorData 확장

```typescript
// 기존 useSensorData.ts에 추가할 부분

// SSE control 이벤트 리스너 추가
es.addEventListener('control', (e) => {
  const controlEvent = JSON.parse(e.data) as ControlEvent;
  // 외부에서 전달받은 콜백으로 처리
  onControlEvent?.(controlEvent);
});
```

**변경 방식**: useSensorData의 반환값에 `onControlEvent` 콜백 등록 메커니즘 추가. 또는 별도 SSE 연결 대신, **useManualControl 안에서 동일한 SSE 스트림을 구독**하는 방식도 가능. (기존 EventSource 인스턴스를 공유하면 연결 1개로 유지)

**선택: useSensorData 확장 방식** — 기존 SSE 연결을 재사용하여 연결 수 최소화.

---

## 5. Relay Server Design Detail

### 5.1 control_store.py 상세

```python
# iot_relay_server/app/control_store.py

import json
import os
from datetime import datetime, timezone
from app.store import _broadcast

CONTROL_STATE_FILE = "control_state.json"

# 인메모리 상태
control_state: dict = { ... }  # §2.1 참조
pending_commands: dict = {}
control_history: list[dict] = []

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _save_state():
    """파일로 영속화 — Docker 재시작 시 복원용"""
    with open(CONTROL_STATE_FILE, "w") as f:
        json.dump(control_state, f)

def _load_state():
    """서버 시작 시 마지막 상태 복원"""
    if os.path.exists(CONTROL_STATE_FILE):
        with open(CONTROL_STATE_FILE) as f:
            saved = json.load(f)
            control_state.update(saved)

def update_control_state(control_type: str, values: dict, source: str):
    """제어 상태 업데이트 + 이력 기록 + 파일 저장"""
    state = control_state[control_type]
    for key, val in values.items():
        if key in state:
            state[key] = val
    state["source"] = source
    state["updated_at"] = _now_iso()

    # active 플래그 자동 설정
    if control_type == "ventilation":
        state["active"] = state.get("window_open_pct", 0) > 0 or state.get("fan_speed", 0) > 0
        state["led_on"] = state["active"]
    elif control_type == "irrigation":
        state["active"] = state.get("valve_open", False)
        state["led_on"] = state["active"]
    elif control_type == "lighting":
        state["active"] = state.get("on", False)
        state["led_on"] = state["active"]
    elif control_type == "shading":
        state["active"] = state.get("shade_pct", 0) > 0 or state.get("insulation_pct", 0) > 0
        state["led_on"] = state["active"]

    # 이력 기록 (최근 100건)
    control_history.append({
        "control_type": control_type,
        "state": dict(state),
        "source": source,
        "timestamp": _now_iso(),
    })
    if len(control_history) > 100:
        control_history[:] = control_history[-100:]

    _save_state()

def add_pending_command(control_type: str, action: dict):
    """ESP8266이 폴링으로 가져갈 명령 추가 (최신 상태 덮어쓰기)"""
    pending_commands[control_type] = {
        **action,
        "timestamp": _now_iso(),
    }

def get_and_clear_pending(device_id: str) -> dict:
    """ESP8266이 명령을 가져가면 큐 클리어"""
    if not pending_commands:
        return {}
    commands = dict(pending_commands)
    return commands

def clear_acknowledged(control_types: list[str]):
    """ACK 받은 명령만 큐에서 제거"""
    for ct in control_types:
        pending_commands.pop(ct, None)

def get_control_state() -> dict:
    return dict(control_state)
```

### 5.2 control_routes.py 상세

```python
# iot_relay_server/app/control_routes.py

from fastapi import APIRouter, Depends, Query
from app.main import verify_api_key  # 기존 API Key 검증 재사용
from app.schemas import ControlCommandIn, ControlReportIn, ControlAckIn
from app.store import _broadcast
from app.control_store import (
    update_control_state,
    add_pending_command,
    get_and_clear_pending,
    clear_acknowledged,
    get_control_state,
    control_state,
    _now_iso,
)

control_router = APIRouter(prefix="/api/v1/control", tags=["control"])

@control_router.post("")
async def send_control(data: ControlCommandIn):
    update_control_state(data.control_type, data.action, data.source)
    add_pending_command(data.control_type, data.action)
    _broadcast("control", {
        "control_type": data.control_type,
        "state": control_state[data.control_type],
        "source": data.source,
        "timestamp": _now_iso(),
    })
    return {"status": "ok", "state": control_state[data.control_type]}

@control_router.get("/state")
async def get_state():
    return get_control_state()

@control_router.get("/commands", dependencies=[Depends(verify_api_key)])
async def get_commands(device_id: str = Query(...)):
    commands = get_and_clear_pending(device_id)
    return {"commands": commands, "timestamp": _now_iso()}

@control_router.post("/report", dependencies=[Depends(verify_api_key)])
async def report_state(data: ControlReportIn):
    update_control_state(data.control_type, data.state, data.source)
    _broadcast("control", {
        "control_type": data.control_type,
        "state": control_state[data.control_type],
        "source": data.source,
        "timestamp": _now_iso(),
    })
    return {"status": "ok"}

@control_router.post("/ack", dependencies=[Depends(verify_api_key)])
async def ack_commands(data: ControlAckIn):
    clear_acknowledged(data.acknowledged_types)
    return {"status": "ok"}
```

### 5.3 main.py 수정

```python
# iot_relay_server/app/main.py 에 추가

from app.control_routes import control_router
from app.control_store import _load_state

# 서버 시작 시 제어 상태 복원
@app.on_event("startup")
async def startup():
    _load_state()

# 라우터 등록 (기존 라우터들 다음에)
app.include_router(control_router)
```

---

## 6. ESP8266 Firmware Design

### 6.1 현재 상태 vs 변경 계획

| 항목 | 현재 | 변경 후 |
|------|------|---------|
| **센서 루프** | 30초 간격 POST /sensors | 유지 (변경 없음) |
| **폴링 루프** | 없음 | 2~3초 간격 GET /control/commands |
| **버튼 처리** | 없음 | 인터럽트 + 디바운싱 → POST /control/report |
| **LED 출력** | 없음 | 명령 수신 또는 버튼 누름 시 LED ON/OFF |
| **핀 사용** | D4(DHT11), A0(LDR) | + D1~D8 중 버튼/LED용 (Phase별) |

### 6.2 펌웨어 구조 변경

```cpp
// DH11_KY018_WiFi.ino — 변경 후 구조

// === 기존 (유지) ===
#define DHT_PIN D4
#define LDR_PIN A0
unsigned long lastSensorPost = 0;
const unsigned long SENSOR_INTERVAL = 30000;  // 30초

// === 신규 (추가) ===
// Phase 1: 환기 LED/버튼
#define VENT_LED_PIN D1
#define VENT_BTN_PIN D2
// Phase 2~4는 해당 Phase 구현 시 주석 해제
// #define IRR_LED_PIN D5
// #define IRR_BTN_PIN D6
// #define LIGHT_LED_PIN D7
// #define LIGHT_BTN_PIN D8
// #define SHADE_LED_PIN D3
// #define SHADE_BTN_PIN D0

unsigned long lastControlPoll = 0;
const unsigned long CONTROL_POLL_INTERVAL = 3000;  // 3초

// 버튼 디바운싱
volatile bool ventButtonPressed = false;
unsigned long lastVentButtonTime = 0;
#define DEBOUNCE_MS 200

// LED 상태
bool ventLedState = false;

void setup() {
  // 기존 센서 초기화 유지
  // ...

  // 버튼/LED 초기화 (Phase 1)
  pinMode(VENT_LED_PIN, OUTPUT);
  pinMode(VENT_BTN_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(VENT_BTN_PIN), ventButtonISR, FALLING);
}

void loop() {
  unsigned long now = millis();

  // 1. 기존 센서 전송 (30초)
  if (now - lastSensorPost >= SENSOR_INTERVAL) {
    postSensorData();
    lastSensorPost = now;
  }

  // 2. 제어 명령 폴링 (3초)
  if (now - lastControlPoll >= CONTROL_POLL_INTERVAL) {
    pollControlCommands();
    lastControlPoll = now;
  }

  // 3. 버튼 이벤트 처리 (인터럽트 플래그 확인)
  if (ventButtonPressed) {
    ventButtonPressed = false;
    handleVentButton();
  }
}

// 버튼 인터럽트 핸들러
ICACHE_RAM_ATTR void ventButtonISR() {
  if (millis() - lastVentButtonTime > DEBOUNCE_MS) {
    ventButtonPressed = true;
    lastVentButtonTime = millis();
  }
}

// 제어 명령 폴링
void pollControlCommands() {
  // GET /api/v1/control/commands?device_id=esp8266-01
  // 명령 있으면 LED 상태 변경 + POST /control/ack
}

// 버튼 눌림 처리
void handleVentButton() {
  ventLedState = !ventLedState;
  digitalWrite(VENT_LED_PIN, ventLedState ? HIGH : LOW);
  // POST /api/v1/control/report
}
```

### 6.3 하드웨어 미구성 대응 (현재 상태)

ESP8266 펌웨어에서 하드웨어가 없는 동안의 처리:

```cpp
// 컴파일 플래그로 하드웨어 활성화 제어
#define HARDWARE_BUTTONS_ENABLED false  // 회로 구성 후 true로 변경

void setup() {
  // 기존 센서 초기화...

  #if HARDWARE_BUTTONS_ENABLED
    pinMode(VENT_LED_PIN, OUTPUT);
    pinMode(VENT_BTN_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(VENT_BTN_PIN), ventButtonISR, FALLING);
  #endif
}

void loop() {
  // 센서 전송은 항상 동작
  // 폴링 루프도 항상 동작 (하드웨어 없어도 명령 수신/ACK 가능)
  // 버튼/LED는 HARDWARE_BUTTONS_ENABLED일 때만

  #if HARDWARE_BUTTONS_ENABLED
    if (ventButtonPressed) { ... }
  #endif
}
```

---

## 7. Communication Flow

### 7.1 Flow A: 프론트엔드 → ESP8266 (원격 제어)

```
사용자 (브라우저)
    │ 환기 슬라이더 70%로 조작
    v
ManualControlPanel
    │ sendCommand("ventilation", {window_open_pct: 70})
    v
useManualControl
    │ POST /api/v1/control
    v
Relay Server (control_routes.py)
    ├─ update_control_state() → 인메모리 업데이트
    ├─ add_pending_command()  → ESP8266용 큐에 추가
    └─ _broadcast("control") → SSE 이벤트 전송
          │
          ├──→ Frontend (SSE) → UI 즉시 반영 (낙관적 업데이트)
          │
          └──→ (대기)
                    │
ESP8266 (2~3초 후 폴링)
    │ GET /api/v1/control/commands
    v
    명령 수신 → LED ON + POST /control/ack
```

**응답 시간**: UI 즉시 반영 + ESP8266 LED 반응 최대 ~5초 (폴링 주기)

### 7.2 Flow B: ESP8266 → 프론트엔드 (버튼 제어)

```
사용자 (현장)
    │ 환기 버튼 누름
    v
ESP8266
    │ 인터럽트 → LED 토글 → POST /api/v1/control/report
    v
Relay Server (control_routes.py)
    ├─ update_control_state() → 인메모리 업데이트
    └─ _broadcast("control") → SSE 이벤트 전송
          │
          v
Frontend (SSE)
    │ control 이벤트 수신
    v
useManualControl.handleControlEvent()
    │ controlState 업데이트
    v
ManualControlPanel → UI 즉시 반영
```

**응답 시간**: ~1~2초 (네트워크 왕복 + SSE 전달)

### 7.3 Flow C: 시뮬레이션 모드 (하드웨어 없이 테스트)

```
사용자 (브라우저, 시뮬레이션 모드 ON)
    │ [환기 버튼 시뮬레이션] 클릭
    v
ManualControlPanel
    │ simulateButton("ventilation")
    v
useManualControl
    │ POST /api/v1/control/report  ← ESP8266 대신 프론트엔드가 직접 호출
    │ { device_id: "simulator", control_type: "ventilation",
    │   state: { led_on: true, active: true }, source: "button" }
    v
Relay Server
    ├─ update_control_state()
    └─ _broadcast("control") → SSE
          │
          v
Frontend → UI 반영 (양방향 흐름 전체 테스트 완료)
```

---

## 8. Test Plan

### 8.1 하드웨어 미구성 단계 테스트 (현재)

| # | 테스트 | 방법 | 기대 결과 |
|---|--------|------|-----------|
| T0-1 | Relay API 동작 | curl POST /control | 200 + state 반환 |
| T0-2 | SSE control 이벤트 | curl -N /sensors/stream + 별도 터미널에서 POST /control | SSE에 control 이벤트 수신 |
| T0-3 | 프론트엔드 UI 렌더링 | 브라우저에서 IoT 대시보드 | ManualControlPanel 표시 |
| T0-4 | 프론트엔드 → SSE 반영 | UI에서 환기 토글 | 슬라이더 값 즉시 반영 |
| T0-5 | 시뮬레이션 모드 | 시뮬레이션 ON → 환기 버튼 클릭 | LED 상태 + 소스 "버튼"으로 변경 |
| T0-6 | 상태 영속화 | Relay Server 재시작 후 GET /control/state | 마지막 상태 복원 |

### 8.2 Phase별 하드웨어 테스트 (회로 구성 후)

| Phase | 테스트 | 성공 기준 |
|-------|--------|-----------|
| 1 | 프론트엔드 환기 ON → ESP8266 LED 점등 | 5초 이내 |
| 1 | ESP8266 환기 버튼 → 프론트엔드 반영 | 2초 이내 |
| 2 | 프론트엔드 밸브 열림 → ESP8266 관수 LED | 5초 이내 |
| 2 | ESP8266 관수 버튼 → 프론트엔드 반영 | 2초 이내 |
| 3 | 프론트엔드 조명 ON → ESP8266 조명 LED | 5초 이내 |
| 4 | 4개 제어 동시 조작 → 상태 정합성 | 모든 상태 일치 |

### 8.3 curl 테스트 커맨드

```bash
# 1. 프론트엔드 제어 시뮬레이션
curl -X POST http://iot.lilpa.moe:9000/api/v1/control \
  -H "Content-Type: application/json" \
  -d '{"control_type":"ventilation","action":{"active":true,"window_open_pct":70},"source":"manual"}'

# 2. 상태 조회
curl http://iot.lilpa.moe:9000/api/v1/control/state

# 3. ESP8266 폴링 시뮬레이션
curl -H "X-API-Key: farmos-iot-default-key" \
  "http://iot.lilpa.moe:9000/api/v1/control/commands?device_id=esp8266-01"

# 4. ESP8266 버튼 보고 시뮬레이션
curl -X POST http://iot.lilpa.moe:9000/api/v1/control/report \
  -H "Content-Type: application/json" \
  -H "X-API-Key: farmos-iot-default-key" \
  -d '{"device_id":"esp8266-01","control_type":"ventilation","state":{"led_on":true,"active":true,"window_open_pct":100},"source":"button"}'

# 5. SSE 스트림 모니터링 (별도 터미널)
curl -N http://iot.lilpa.moe:9000/api/v1/sensors/stream
```

---

## 9. Phase별 구현 순서

### Phase 1: 환기 (전체 인프라 구축)

**순서 (Software-First):**

1. Relay Server: `control_store.py` 생성 (인메모리 상태 + 파일 영속화)
2. Relay Server: `schemas.py`에 제어 스키마 추가
3. Relay Server: `control_routes.py` 생성 (5개 API)
4. Relay Server: `main.py`에 라우터 등록 + startup 이벤트
5. **→ N100 업로드 + Docker 재시작 (사용자 작업)**
6. curl로 API 테스트 (T0-1, T0-2)
7. Frontend: `types/index.ts`에 타입 추가
8. Frontend: `useManualControl.ts` 훅 생성
9. Frontend: `useSensorData.ts` SSE control 이벤트 추가
10. Frontend: `ManualControlPanel.tsx` 생성 (환기만 활성, 시뮬레이션 모드 포함)
11. Frontend: `IoTDashboardPage.tsx`에 ManualControlPanel 임포트
12. 브라우저에서 시뮬레이션 모드 테스트 (T0-3 ~ T0-5)
13. ESP8266: 폴링 루프 추가 (HARDWARE_BUTTONS_ENABLED=false)
14. **→ 회로 구성 후: 버튼/LED 배선 + HARDWARE_BUTTONS_ENABLED=true**
15. 실물 양방향 테스트

### Phase 2~4: 관수 → 조명 → 차광

각 Phase에서 추가 작업:
- `ManualControlPanel`에 해당 제어 카드 활성화
- ESP8266에 해당 버튼/LED 핀 define + ISR 추가
- Relay Server 변경 없음 (이미 4개 제어 타입 모두 지원)

---

## 10. Deployment Notes

### 10.1 변경 대상별 배포 절차

| 대상 | 변경 파일 | 배포 방식 | 비고 |
|------|-----------|-----------|------|
| **Relay Server** | control_store.py, control_routes.py, schemas.py, main.py | N100에 업로드 → Docker 재빌드 | **사용자 직접 수행** |
| **Frontend** | ManualControlPanel.tsx, useManualControl.ts, useSensorData.ts, types/index.ts, IoTDashboardPage.tsx | 로컬 `npm run dev` 자동 반영 | 핫 리로드 |
| **ESP8266** | DH11_KY018_WiFi.ino | Arduino IDE → 시리얼 업로드 | **사용자 직접 수행** |

### 10.2 Relay Server 배포 명령

```bash
# N100 서버에서 실행
cd iot_relay_server
docker compose down
docker compose up -d --build

# 헬스체크
curl http://iot.lilpa.moe:9000/health

# 제어 API 확인
curl http://iot.lilpa.moe:9000/api/v1/control/state
```

> **서버 직접 조작 금지** — 코드 수정 후 사용자에게 위 절차 안내

---

## 11. Implementation Guide

### 11.1 Module Map

| Module | 범위 | 파일 수 | 의존성 |
|--------|------|---------|--------|
| **module-1** | Relay Server 제어 API | 4 (control_store.py, control_routes.py, schemas.py 수정, main.py 수정) | 없음 (독립) |
| **module-2** | Frontend 훅 + 타입 | 3 (useManualControl.ts, useSensorData.ts 수정, types/index.ts 수정) | module-1 완료 필요 |
| **module-3** | Frontend UI 컴포넌트 | 2 (ManualControlPanel.tsx, IoTDashboardPage.tsx 수정) | module-2 완료 필요 |
| **module-4** | ESP8266 펌웨어 | 1 (DH11_KY018_WiFi.ino 수정) | module-1 완료 필요 |

### 11.2 Recommended Session Plan

| Session | Module | 예상 작업 | 배포 필요 |
|---------|--------|-----------|-----------|
| **Session 1** | module-1 | Relay Server 코드 작성 → N100 배포 요청 → curl 테스트 | Relay Server (N100) |
| **Session 2** | module-2 + module-3 | Frontend 훅/타입/UI 구현 → 시뮬레이션 모드 테스트 | 없음 (로컬 핫 리로드) |
| **Session 3** | module-4 | ESP8266 펌웨어 수정 → 하드웨어 배선 → 실물 테스트 | ESP8266 (시리얼 업로드) |

### 11.3 Session Guide

```
/pdca do iot-manual-control --scope module-1        # Relay Server API
/pdca do iot-manual-control --scope module-2,module-3  # Frontend 전체
/pdca do iot-manual-control --scope module-4        # ESP8266 펌웨어
```

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-16 | Initial draft — Option C (Pragmatic Balance) | clover0309 |
| 0.2 | 2026-04-23 | Code Sync — Status 를 Production 으로 상향. Relay `control_store.py` 영속화(`control_state.json` 파일) 와 `control_routes.py` 5개 엔드포인트는 `iot-relay-server-plan.md §4.3` 에 공식 엔드포인트로 등록됨. FE 시뮬레이션 모드(`simulateButton` → `POST /control/report`) 동작 확인. ESP8266 폴링 루프는 `HARDWARE_BUTTONS_ENABLED` 컴파일 플래그로 비활성 상태 유지. | clover0309 |
