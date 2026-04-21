# Manual Control ON/OFF Design Document

> **Feature**: manual-control-onoff
> **Architecture**: Option C — Pragmatic (훅 ref + 카드 조립)
> **Plan Reference**: `FarmOS/docs/01-plan/features/manual-control-onoff.plan.md`
> **Version**: 0.1.0
> **Author**: clover0309 (CTO Lead orchestrated)
> **Date**: 2026-04-21
> **Status**: Draft
> **Level**: Dynamic (FarmOS)
> **Prerequisites**: `iot-manual-control` 피처 완료 (4대 제어 카드 + `/control` API + `useManualControl` 훅 존재)

---

## Context Anchor

> Plan 문서에서 전파. Do/Check 단계에서 WHY를 잃지 않기 위한 앵커.

| Key | Value |
|-----|-------|
| **WHY** | 4대 제어 카드 중 조명만 ON/OFF 마스터 스위치 보유 → UX 비일관성 + 전체 차단/복원 워크플로우 부재 |
| **WHO** | FarmOS 대시보드 1인 농업인 운용자, `ManualControlPanel`의 환기/차광 카드 직접 조작 |
| **RISK** | (1) `active` vs `on` 의미 혼동 (2) 복원 대상 없을 때 프리셋 결정 (3) `simulateButton` 경로와 수동 토글 경로의 상태 불일치 |
| **SUCCESS** | 환기/차광에 조명과 동일 패턴 ON/OFF 버튼 + OFF=모두 0 + ON=이전값(없으면 프리셋) + 조명/관수 회귀 0건 + ESP8266/Relay Server 코드 변경 0줄 |
| **SCOPE** | Frontend 3파일: `types/index.ts`, `hooks/useManualControl.ts`, `modules/iot/ManualControlPanel.tsx`. 예상 증분 ~95 lines |

---

## Decision Record

- **선택**: Option C — Pragmatic
- **검토 일자**: 2026-04-21
- **채택 근거**:
  1. LightingCard가 이미 `onCommand({ on: !state.on, brightness_pct: !state.on ? 60 : 0 })` 형태로 카드 내부에서 payload를 조립 → 동형 패턴 복제가 가장 자연스럽다
  2. 훅의 기존 8개 export 시그니처 불변 (신규 `lastKnownValuesRef` 한 개만 추가) → 다른 consumer 회귀 0
  3. `simulateButton` switch 문에서 `lastKnownValuesRef.current` 갱신 한 줄만 추가하면 수동/시뮬 두 경로가 동일 ref 공유
  4. 증분 ~95 lines로 Plan NFR `<120 lines` 충족
- **기각 사유**:
  - Option A (Minimal): `simulateButton`의 훅 내부 로직과 카드의 로컬 ref가 분리되어 시뮬 후 복원값 어긋남 위험
  - Option B (Clean): 훅 리팩터 여파 중간, 현재 규모(카드 2개)에서 과도한 투자. 4대 카드 전체 확장 계획이 생기면 B로 재평가 가치

---

## 1. Overview

### 1.1 Purpose

환기(Ventilation)와 차광/보온(Shading) 카드에 조명(Lighting) 카드와 동일한 ON/OFF 마스터 스위치 버튼을 추가하여 4대 제어 카드의 UX를 균일화한다. 구현은 React 훅 하나(`useManualControl`)에 ref 하나를 추가하고, 두 카드에 토글 UI + payload 조립 로직을 삽입하는 방식으로 수행한다.

### 1.2 Scope Reference

- In Scope: Plan §2.1 전수 반영
- Out of Scope: ESP8266 펌웨어, Relay Server API, 데이터베이스 스키마, 인증 방식, IrrigationCard/LightingCard 로직 변경

---

## 2. Architecture

### 2.1 선택: Option C — Pragmatic (훅 ref + 카드 조립)

책임 분리:

```
┌────────────────────────────────────────────────────────────────┐
│ useManualControl (hook)                                        │
│  ├─ controlState (기존)                                         │
│  ├─ sendCommandImmediate(controlType, action)   (기존, 재사용)   │
│  ├─ simulateButton(controlType)                 (기존 + ref 갱신)│
│  └─ lastKnownValuesRef                          ◄── NEW export  │
│       { ventilation?: {window_open_pct, fan_speed},            │
│         shading?:     {shade_pct, insulation_pct} }            │
└────────────────────────────────────────────────────────────────┘
                │
                ▼ props.lastKnownRef
┌────────────────────────────────────────────────────────────────┐
│ VentilationCard / ShadingCard                                  │
│  ├─ handleMasterToggle()                         ◄── NEW       │
│  │    if (state.on) {                                           │
│  │      lastKnownRef.current[X] = { 현재 슬라이더값 }            │
│  │      onCommand({ 슬라이더=0, on:false, led_on:false })       │
│  │    } else {                                                  │
│  │      const vals = lastKnownRef.current[X] ?? PRESET          │
│  │      onCommand({ ...vals, on:true, led_on:true })            │
│  │    }                                                         │
│  └─ LightingCard 패턴 복제 ON/OFF 버튼 (blue-500 / emerald-500) │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 책임 경계

| 계층 | 책임 |
|------|------|
| `types/index.ts` | 데이터 계약: `VentilationState.on`, `ShadingState.on` 필드 추가 |
| `useManualControl` | 세션 상태 보관 (ref), API 호출, `simulateButton` 정합성 유지 |
| `VentilationCard`/`ShadingCard` | UI 렌더링, toggle 의도 해석, `/control` payload 조립 |
| `ManualControlPanel` | 컴포지션: 훅 → 카드로 `lastKnownRef` 전달 |

### 2.3 LightingCard와의 동형성

LightingCard(L215-L262)는 이미 아래 구조:
```tsx
<button onClick={() => onCommand({ on: !state.on, brightness_pct: !state.on ? 60 : 0 })}>
  {state.on ? 'ON' : 'OFF'}
</button>
<ControlSlider value={state.brightness_pct} onChange={...} disabled={!state.on} />
```
VentilationCard/ShadingCard도 동일 패턴 + 다중 슬라이더 대응 + ref 기반 복원 값만 추가.

---

## 3. Data Model

### 3.1 Types Diff (`FarmOS/frontend/src/types/index.ts`)

```ts
// BEFORE
export interface VentilationState extends ControlItemState {
  window_open_pct: number;
  fan_speed: number;
}

export interface ShadingState extends ControlItemState {
  shade_pct: number;
  insulation_pct: number;
}

// AFTER
export interface VentilationState extends ControlItemState {
  window_open_pct: number;
  fan_speed: number;
  on: boolean;              // NEW — 마스터 스위치 (ESP8266 active와 별개)
}

export interface ShadingState extends ControlItemState {
  shade_pct: number;
  insulation_pct: number;
  on: boolean;              // NEW — 마스터 스위치
}
```

### 3.2 필드 의미 명확화

| 필드 | 의미 | 출처 |
|------|------|------|
| `active` (기존, ControlItemState) | ESP8266 **하드웨어 버튼** 누름 상태 | `simulateButton`/하드웨어 `/control/report` |
| `on` (신규) | 프론트엔드 **마스터 스위치** 상태 | 카드 ON/OFF 버튼 클릭, SSE로 동기화 |
| `led_on` (기존) | 실제 LED 켜짐 여부 | 서버/하드웨어 상태 보고 |

> **혼동 방지 원칙**: `on` = 사용자 의도, `active` = 하드웨어 현재 상태, `led_on` = 물리 LED. 세 필드는 대체로 일치하지만 중간 상태(명령 전송 중)에서는 다를 수 있다.

### 3.3 관수/조명 영향

- `IrrigationControlState.valve_open` — 이미 마스터 스위치 역할, 변경 없음
- `LightingState.on` — 이미 존재, 변경 없음
- 두 인터페이스 모두 diff 0

---

## 4. API Contract

### 4.1 `/api/v1/control` POST

기존 엔드포인트 그대로 사용. 클라이언트가 `on` 필드를 payload에 포함할 수 있으며, 서버는 모르는 필드는 무시해도 무방(forward-compatible).

```http
POST /api/v1/control
Content-Type: application/json

{
  "control_type": "ventilation",
  "action": {
    "window_open_pct": 100,
    "fan_speed": 1500,
    "on": true,
    "led_on": true
  },
  "source": "manual"
}
```

### 4.2 Payload 예시 (4가지)

| 액션 | control_type | action |
|------|--------------|--------|
| 환기 ON (복원) | ventilation | `{window_open_pct: <lastKnown 또는 100>, fan_speed: <lastKnown 또는 1500>, on: true, led_on: true}` |
| 환기 OFF | ventilation | `{window_open_pct: 0, fan_speed: 0, on: false, led_on: false}` |
| 차광 ON (복원) | shading | `{shade_pct: <lastKnown 또는 50>, insulation_pct: <lastKnown 또는 0>, on: true, led_on: true}` |
| 차광 OFF | shading | `{shade_pct: 0, insulation_pct: 0, on: false, led_on: false}` |

### 4.3 SSE `control` 이벤트

기존 구조 그대로. `state` 페이로드에 `on` 필드가 들어올 수도, 안 들어올 수도 있음. 들어오지 않으면 기존 state 유지(`{...prev, ...event.state}` 스프레드 방식이라 자동 호환).

---

## 5. Hook Changes (`useManualControl.ts`)

### 5.1 신규 ref

```ts
// 기존 debounceTimers, manualTimestamps 근처에 추가
const lastKnownValuesRef = useRef<Partial<{
  ventilation: { window_open_pct: number; fan_speed: number };
  shading: { shade_pct: number; insulation_pct: number };
}>>({});
```

### 5.2 `simulateButton` 정합성 1줄

기존 `simulateButton` 내 switch 문의 `ventilation`/`shading` case에서 `newActive=false`로 가는 상황에 ref 업데이트:

```ts
case 'ventilation':
  if (!newActive) {
    // 시뮬레이션 OFF 시: 현재 값을 ref에 저장 (수동 ON 토글 시 복원 가능)
    lastKnownValuesRef.current.ventilation = {
      window_open_pct: current.window_open_pct,
      fan_speed: current.fan_speed,
    };
  }
  toggleState = { window_open_pct: newActive ? 100 : 0, fan_speed: newActive ? 1500 : 0, on: newActive };
  break;
case 'shading':
  if (!newActive) {
    lastKnownValuesRef.current.shading = {
      shade_pct: current.shade_pct,
      insulation_pct: current.insulation_pct,
    };
  }
  toggleState = { shade_pct: newActive ? 50 : 0, insulation_pct: 0, on: newActive };
  break;
```

> **기존 동작 보존**: `irrigation`, `lighting` case는 변경 없음. `on` 필드만 `toggleState`에 한 줄 추가 (ventilation/shading/lighting — lighting은 이미 `on: newActive` 존재).

### 5.3 반환값 확장

```ts
return {
  controlState,
  simMode,
  setSimMode,
  loading,
  sendCommand,
  sendCommandImmediate,
  simulateButton,
  unlockControl,
  handleControlEvent,
  refetch: fetchState,
  lastKnownValuesRef,    // NEW
};
```

### 5.4 `fetchState` 응답 호환 처리

서버가 `on` 필드를 반환하지 않는 경우 방어:
```ts
// fetchState 내부, setControlState(data) 직전
const normalized = {
  ...data,
  ventilation: { ...data.ventilation, on: data.ventilation.on ?? data.ventilation.led_on ?? false },
  shading:     { ...data.shading,     on: data.shading.on     ?? data.shading.led_on     ?? false },
};
setControlState(normalized);
```

---

## 6. UI Changes (`ManualControlPanel.tsx`)

### 6.1 VentilationCard

```tsx
// Design Ref: §6.1 — VentilationCard ON/OFF 마스터 스위치 추가
function VentilationCard({
  state,
  lastKnownRef,
  onSlider,
  onButton,
  onCommand,
  onUnlock,
}: {
  state: ManualControlState['ventilation'];
  lastKnownRef: React.MutableRefObject<Partial<{
    ventilation: { window_open_pct: number; fan_speed: number };
    shading: { shade_pct: number; insulation_pct: number };
  }>>;
  onSlider: (action: Record<string, unknown>) => void;
  onButton: (action: Record<string, unknown>) => void;
  onCommand: (action: Record<string, unknown>) => void;
  onUnlock: () => void;
}) {
  const handleMasterToggle = () => {
    if (state.on) {
      lastKnownRef.current.ventilation = {
        window_open_pct: state.window_open_pct,
        fan_speed: state.fan_speed,
      };
      onCommand({ window_open_pct: 0, fan_speed: 0, on: false, led_on: false });
    } else {
      const vals = lastKnownRef.current.ventilation ?? { window_open_pct: 100, fan_speed: 1500 };
      onCommand({ ...vals, on: true, led_on: true });
    }
  };

  return (
    <div className={`bg-white rounded-xl border p-4 space-y-3 ${state.locked ? 'ring-1 ring-orange-300' : ''}`}>
      <div className="flex items-center gap-2">
        <MdAir className="text-xl text-blue-500" />
        <span className="font-semibold text-gray-800 text-sm">환기</span>
        <LedIndicator on={state.led_on} />
        <SourceBadge source={state.source} />
        <LockButton locked={state.locked} onToggle={onUnlock} />
      </div>

      {/* NEW — 상단 ON/OFF 마스터 스위치 (LightingCard L234-246 동형) */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-600">상태</span>
        <button
          onClick={handleMasterToggle}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
            state.on ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
          }`}
        >
          {state.on ? 'ON' : 'OFF'}
        </button>
      </div>

      <div>
        <div className="flex justify-between text-sm text-gray-600 mb-1">
          <span>창문 개폐율</span>
          <span className="font-semibold text-gray-800">{state.window_open_pct}%</span>
        </div>
        <ControlSlider
          value={state.window_open_pct}
          onChange={(v) => onSlider({ window_open_pct: v, on: v > 0 })}
          color="blue-500"
          disabled={!state.on}   /* NEW — OFF 시 비활성 */
        />
      </div>

      {/* 팬 속도 프리셋은 기존 그대로 (단 모든 onButton payload에 on: rpm>0 추가) */}
      <div className="flex justify-between text-sm text-gray-600">
        <span>팬 속도</span>
        <span className="font-semibold text-gray-800">{state.fan_speed} RPM</span>
      </div>
      <div className="flex gap-1">
        {[0, 500, 1000, 1500, 3000].map((rpm) => (
          <button
            key={rpm}
            onClick={() => onButton({ fan_speed: rpm, on: rpm > 0 || state.window_open_pct > 0 })}
            className={`flex-1 text-xs py-1 rounded ${
              state.fan_speed === rpm
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
            disabled={!state.on && rpm > 0}
          >
            {rpm === 0 ? 'OFF' : rpm}
          </button>
        ))}
      </div>
    </div>
  );
}
```

### 6.2 ShadingCard

동일 패턴, accent=emerald-500, 필드=`shade_pct`/`insulation_pct`, 프리셋=`{shade_pct: 50, insulation_pct: 0}`.

### 6.3 최상위 Panel에서 ref prop 전달

```tsx
const {
  controlState, simMode, setSimMode, loading,
  sendCommand, sendCommandImmediate, simulateButton, unlockControl, handleControlEvent,
  lastKnownValuesRef,        // NEW
} = useManualControl();

// 카드 렌더링 부분
<VentilationCard
  state={controlState.ventilation}
  lastKnownRef={lastKnownValuesRef}       /* NEW */
  onSlider={(action) => sendCommand('ventilation', action)}
  onButton={(action) => sendCommandImmediate('ventilation', action)}
  onCommand={(action) => sendCommandImmediate('ventilation', action)}   /* NEW prop for master toggle */
  onUnlock={() => unlockControl('ventilation')}
/>
<ShadingCard
  state={controlState.shading}
  lastKnownRef={lastKnownValuesRef}       /* NEW */
  onCommand={(action) => sendCommandImmediate('shading', action)}       /* 기존 sendCommand → sendCommandImmediate 변경: master toggle은 즉시 전송 */
  onSlider={(action) => sendCommand('shading', action)}                  /* 슬라이더는 여전히 디바운스 */
  onUnlock={() => unlockControl('shading')}
/>
```

> **주의**: ShadingCard는 기존에 `onCommand={(action) => sendCommand('shading', action)}` (디바운스)만 받았다. 이제 슬라이더용(디바운스) + 마스터용(즉시) 두 prop을 분리해 받는다.

### 6.4 IrrigationCard / LightingCard — diff 0

이 두 카드는 **한 줄도 건드리지 않는다**. 회귀 테스트로 확인.

---

## 7. State Flow

### 7.1 수동 OFF 토글 시퀀스

```
User clicks [OFF]
   │
   ▼
VentilationCard.handleMasterToggle()
   │
   ├─ lastKnownRef.current.ventilation = { window_open_pct: 80, fan_speed: 1000 }  (현재값 저장)
   │
   ├─ onCommand({ window_open_pct: 0, fan_speed: 0, on: false, led_on: false })
   │    │
   │    ▼
   │  useManualControl._optimisticUpdate(ventilation, action)
   │    → setControlState({ ...prev, ventilation: { ...prev.ventilation, window=0, fan=0, on:false, led_on:false, source:'manual', locked:true } })
   │    → manualTimestamps.current.ventilation = now
   │
   └─ useManualControl._postControl(ventilation, action)
        → POST /api/v1/control
        → 서버가 릴레이 명령 큐에 적재
        → 응답 200 OK
             │
             ▼
        SSE 'control' event 수신 (source: 'manual', state: {window=0, fan=0, led_on:false, on:false})
        → handleControlEvent(event)
        → 5초 내 manual 이벤트이므로 통과 (isAISource=false)
        → setControlState 업데이트 (자기 자신 echo, 변화 없음)
```

### 7.2 수동 ON 토글 시퀀스

```
User clicks [ON]
   │
   ▼
VentilationCard.handleMasterToggle()
   │
   ├─ vals = lastKnownRef.current.ventilation ?? { window_open_pct: 100, fan_speed: 1500 }
   │       // ex. { window_open_pct: 80, fan_speed: 1000 }
   │
   └─ onCommand({ ...vals, on: true, led_on: true })
        → _optimisticUpdate → UI 즉시 반영
        → POST /api/v1/control
        → SSE echo → 동기화 유지
```

### 7.3 AI rule이 수동 OFF를 덮지 못하는 이유

`useManualControl.handleControlEvent`:
```ts
const isAISource = ['rule', 'tool', 'ai'].includes(event.source);
const elapsed = Date.now() - lastManual;
if (isAISource && elapsed < 5000) return;   // 수동 조작 후 5초간 AI 무시
```
→ 사용자가 OFF 누른 직후 5초간 AI rule이 "환기 조건 만족 → window 80%" 같은 명령을 보내도 무시됨. OFF 상태 보호.

### 7.4 시뮬레이션 OFF → 수동 ON 경로

1. `simulateButton('ventilation')` (현재 active=true) → `newActive=false`
2. switch case `ventilation` → `lastKnownValuesRef.current.ventilation = { window: 현재값, fan: 현재값 }` 저장
3. `toggleState = { window=0, fan=0, on:false }` 전송
4. 이후 사용자가 수동 [ON] 클릭
5. `handleMasterToggle()` → ref에 시뮬 저장 값 존재 → 그 값으로 복원
6. → 수동/시뮬 경로 일관성 확보

---

## 8. Test Plan

### 8.1 L1 — API Contract (curl / Vitest fetch mock)

| # | 시나리오 | 요청 | 기대 |
|---|---------|------|------|
| L1-1 | 환기 ON payload | `POST /control {control_type:"ventilation", action:{window_open_pct:100,fan_speed:1500,on:true,led_on:true}, source:"manual"}` | 200 OK |
| L1-2 | 환기 OFF payload | `POST /control {control_type:"ventilation", action:{window_open_pct:0,fan_speed:0,on:false,led_on:false}, source:"manual"}` | 200 OK |
| L1-3 | 차광 ON payload | 동형 | 200 OK |
| L1-4 | 차광 OFF payload | 동형 | 200 OK |
| L1-5 | `/control/state` 응답에 `on` 없을 때 | mock 서버 응답에서 on 필드 제외 | 클라이언트가 `on = led_on ?? false`로 정규화 |

### 8.2 L2 — UI Action (Playwright)

| # | 시나리오 | 기대 |
|---|---------|------|
| L2-1 | 환기 카드 [OFF] 클릭 | 슬라이더 window=0, fan 버튼 OFF 활성, `disabled={!state.on}` 적용 |
| L2-2 | 환기 [OFF] 후 [ON] 클릭 | 슬라이더가 클릭 직전 값으로 복원 (또는 프리셋 100/1500) |
| L2-3 | 차광 [OFF] 후 [ON] | shade_pct/insulation_pct 복원 |
| L2-4 | 환기 슬라이더 80으로 드래그 → [OFF] → [ON] | 80 복원 |

### 8.3 L3 — E2E (Playwright)

| # | 시나리오 | 기대 |
|---|---------|------|
| L3-1 | 환기 [OFF] 후 5초 내 AI rule SSE 도착 | 슬라이더 0 유지 (manualTimestamps 보호) |
| L3-2 | 시뮬레이션 모드 ON → [환기] 시뮬 버튼 → 수동 [ON] | 시뮬 OFF 시점 값으로 복원 |
| L3-3 | 새로고침 후 환기 [ON] 클릭 (ref 비어있음) | 프리셋 (100/1500)으로 복원 |

### 8.4 회귀 테스트 (필수)

| # | 시나리오 | 기대 |
|---|---------|------|
| R-1 | 관수 [열림/닫힘] 토글 | 기존 동작 그대로 (payload에 on 필드 없음) |
| R-2 | 조명 [ON/OFF] + 밝기 슬라이더 | 기존 동작 그대로 |
| R-3 | `/control/state` 초기 fetch 후 관수/조명 카드 렌더 | diff 없음 |

---

## 9. Migration / Rollback

### 9.1 Forward Migration

- 타입 변경 단독 배포 시 컴파일 실패 가능 → 타입 + 훅 fetchState 정규화 + UI를 **단일 PR로 배포**
- 배포 후 기존 세션의 localStorage/쿠키 영향 없음 (ref는 메모리 전용)

### 9.2 Rollback

- 단순 `git revert`로 복구 가능
- Relay Server는 건드리지 않았으므로 배포 롤백 대상 1곳(프론트엔드)
- `on` 필드를 받던 서버가 있더라도 forward-compatible 스키마이므로 롤백 후에도 오류 없음

### 9.3 Data Compatibility

- 기존 서버 응답에 `on` 필드 없어도 `on ?? led_on ?? false` 정규화로 안전
- SSE 이벤트에 `on` 없어도 spread merge로 기존 state 유지

---

## 10. Risks & Mitigations

| # | Risk (Plan) | Mitigation |
|---|-------------|-----------|
| R1 | `active`와 `on` 필드 의미 혼동 | §3.2 필드 의미 표 명시 + 코드 주석 `// NEW - 마스터 스위치 (ESP8266 active와 별개)` |
| R2 | 복원값 없을 때 프리셋 결정 | 프리셋 확정 (환기 100/1500, 차광 50/0) + 카드 내부 nullish coalescing으로 안전 fallback |
| R3 | simulateButton과 수동 토글 경로 불일치 | §5.2에서 `simulateButton` switch에 ref 갱신 1줄씩 삽입하여 동일 ref 공유 |
| R4 | 배포 중 클라이언트는 on 필드 전송, 서버는 모름 | 서버는 unknown 필드 무시(FastAPI Pydantic default) — 확인 필요하나 기존 동작 동일 |

---

## 11. Implementation Guide

### 11.1 파일별 변경 요약

| # | 파일 | 변경 유형 | 예상 라인 |
|---|------|----------|----------|
| 1 | `FarmOS/frontend/src/types/index.ts` | 수정 (2 인터페이스에 `on: boolean` 추가) | +2 |
| 2 | `FarmOS/frontend/src/hooks/useManualControl.ts` | 수정 (ref 추가, simulateButton switch 수정, fetchState 정규화, return 확장) | +15 |
| 3 | `FarmOS/frontend/src/modules/iot/ManualControlPanel.tsx` | 수정 (VentilationCard/ShadingCard + Panel props 전달) | +75 |
| **합계** | | | **~92 lines** (Plan NFR `<120` 충족) |

### 11.2 구현 순서

1. `types/index.ts`에 `VentilationState.on`, `ShadingState.on` 추가 → 컴파일 에러 확인 (훅/카드 미수정 시 빨갛게 뜸)
2. `useManualControl.ts`에 `lastKnownValuesRef` 선언
3. `fetchState` 응답 정규화 코드 추가 (on 필드 없을 때 fallback)
4. `simulateButton` switch의 ventilation/shading case에 ref 갱신 + toggleState에 `on: newActive` 추가
5. `useManualControl` return에 `lastKnownValuesRef` 추가
6. `ManualControlPanel.tsx` 최상위에서 `lastKnownValuesRef` 수신
7. `VentilationCard` props 타입에 `lastKnownRef`, `onCommand` 추가
8. `VentilationCard` 내부에 `handleMasterToggle` + ON/OFF 버튼 JSX + `disabled={!state.on}`
9. `ShadingCard`에 동일 적용 (emerald-500, shade/insulation)
10. Panel에서 두 카드에 `lastKnownRef={lastKnownValuesRef}`, `onCommand={sendCommandImmediate...}` 전달
11. 수동 스모크 테스트: `pnpm dev` → 브라우저에서 환기/차광 ON/OFF 동작 확인
12. 관수/조명 회귀 스모크 (IrrigationCard 열림/닫힘, LightingCard ON/OFF + 밝기 슬라이더)

### 11.3 Session Guide

단일 세션 권장 (총 소요 < 1h). 필요 시 아래 Module Map으로 분할 가능.

| Module Key | 파일 | 작업 | 예상 시간 | 예상 라인 |
|------------|------|------|----------|----------|
| `module-types` | `types/index.ts` | VentilationState/ShadingState에 `on: boolean` 추가 | 5 min | +2 |
| `module-hook` | `hooks/useManualControl.ts` | `lastKnownValuesRef` 선언, `fetchState` 정규화, `simulateButton` switch 수정, return 확장 | 15 min | +15 |
| `module-ui` | `modules/iot/ManualControlPanel.tsx` | VentilationCard/ShadingCard에 ON/OFF 버튼 + ref 연동 + disabled 처리 + Panel 내 prop 전달 | 30 min | +75 |
| `module-smoke` | (실행) | `pnpm dev` 브라우저 수동 검증 + 관수/조명 회귀 확인 | 10 min | 0 |

**권장 실행**: `/pdca do manual-control-onoff` (scope 없이 전체). 필요 시 `--scope module-types,module-hook,module-ui` 분할.

---

## 12. Acceptance Criteria (Design → Do 확인용)

- [ ] VentilationCard 헤더 아래 "상태" row + ON/OFF 버튼 존재 (blue-500)
- [ ] ShadingCard 헤더 아래 "상태" row + ON/OFF 버튼 존재 (emerald-500)
- [ ] ON 클릭 시 이전 값 복원 또는 프리셋 사용
- [ ] OFF 클릭 시 슬라이더 모두 0 + led_on false
- [ ] 슬라이더/프리셋 버튼이 OFF 상태에서 `disabled`
- [ ] `simulateButton` ventilation/shading OFF 시 ref 갱신됨
- [ ] IrrigationCard/LightingCard 코드 diff 0
- [ ] `/control/state` 응답에 on 없어도 에러 없음
- [ ] 관수/조명 회귀 테스트 통과
