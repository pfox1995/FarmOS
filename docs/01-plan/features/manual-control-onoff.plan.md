# Manual Control ON/OFF Planning Document

> **Summary**: 환기/차광·보온 카드에 조명 카드와 동일한 ON/OFF 마스터 스위치 버튼을 추가하여 4대 제어 카드의 UX 일관성을 확보한다. ESP8266 펌웨어와 Relay Server 로직은 변경하지 않는 순수 프론트엔드 피처.
>
> **Project**: FarmOS - Manual Control UX Polish
> **Version**: 0.1.0
> **Author**: clover0309
> **Date**: 2026-04-21
> **Status**: Draft
> **Prerequisites**: `iot-manual-control` 피처 완료 (4대 제어 카드 + Relay Server `/control` API + `useManualControl` 훅 존재)

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | 현재 `ManualControlPanel`의 4대 제어 카드 중 조명(Lighting)만 ON/OFF 마스터 스위치를 가지고 있다. 환기(Ventilation)와 차광/보온(Shading)은 슬라이더/프리셋으로만 제어 가능해 "전체 OFF → 이전 값 복원" 같은 직관적 액션이 불가능하고 UX 일관성이 깨진다. |
| **Solution** | `LightingCard`의 ON/OFF 버튼 패턴을 `VentilationCard`와 `ShadingCard`에 이식하되 색상만 각 카드 accent(blue-500 / emerald-500)에 맞게 교체한다. 이전 슬라이더 값은 React `useRef`로 세션 내 기억하고, OFF 시 전 슬라이더를 0으로, ON 시 기억된 값(없으면 프리셋)으로 복원한다. `on: boolean`을 타입에 신규 추가하며 기존 `active` 필드(ESP8266 하드웨어 버튼 상태)는 책임 분리를 위해 그대로 유지한다. |
| **Function/UX Effect** | 대시보드에서 "환기 OFF" / "차광 OFF" 원클릭으로 모든 관련 슬라이더가 0으로 내려가고 LED가 꺼지며, 다시 ON 클릭 시 마지막으로 작업하던 값이 즉시 복원된다. 4대 카드 모두 동일한 상단 액션 라인업 → 학습 비용 제거 + 회귀 0건. |
| **Core Value** | **UX 일관성 + 빠른 전체 차단/복원 경험**. 1인 농업인이 '지금은 다 끄자' → 잠시 후 '아까처럼 돌리자'라는 흔한 워크플로우를 두 번의 클릭으로 완료. 추가 서버 작업 없이 프론트엔드만으로 달성. |

---

## Context Anchor

> Auto-generated from Executive Summary. Propagated to Design/Do documents for context continuity.

| Key | Value |
|-----|-------|
| **WHY** | 4대 제어 카드 중 조명만 ON/OFF 마스터 스위치를 보유 → UX 비일관성 + '전체 차단/복원' 워크플로우 부재 |
| **WHO** | FarmOS 대시보드 사용자 (1인 농업인), `ManualControlPanel`의 환기·차광 카드를 직접 조작하는 현장 운용자 |
| **RISK** | (1) 기존 `active` 필드와 신규 `on` 필드의 의미 혼동 (2) 복원 대상 값이 없을 때 프리셋 결정 (3) `simulateButton` 경로와 수동 토글 경로의 상태 불일치 |
| **SUCCESS** | 환기/차광 카드에 조명과 동일 패턴 ON/OFF 버튼 존재 + OFF 시 모든 슬라이더 0 + ON 시 이전 값(혹은 프리셋) 복원 + 조명/관수 동작 회귀 0건 + ESP8266/Relay Server 코드 변경 0줄 |
| **SCOPE** | Frontend 전용: `ManualControlPanel.tsx` 카드 2개 수정 + `types` 인터페이스에 `on: boolean` 추가 + (선택) `useManualControl` 훅에 `lastKnownValues` ref 도입 |

---

## 1. Overview

### 1.1 Purpose

`FarmOS` IoT 대시보드의 `ManualControlPanel`에서 **환기(Ventilation)**와 **차광/보온(Shading)** 제어 카드에 ON/OFF 마스터 스위치를 추가하여, 기존 조명(Lighting) 카드와 동일한 UX를 제공한다. 사용자가 한 번의 클릭으로 해당 제어의 모든 파라미터를 0으로 만들거나(OFF), OFF 직전에 사용하던 값으로 복원하는(ON) 액션을 지원한다.

### 1.2 Background

- **선행 피처**: `iot-manual-control`에서 4대 제어 카드(환기/관수/조명/차광), Relay Server `/control` API, ESP8266 폴링 경로, `useManualControl` 훅이 모두 완성되었다.
- **현재 UX 비대칭**: `LightingCard`만 `on: boolean` 필드와 상단 ON/OFF 토글을 가지고 있다. 나머지 3개 카드 중 관수(`IrrigationCard`)는 밸브 열림/닫힘 토글이 자연스럽게 ON/OFF 역할을 하지만, 환기와 차광은 **여러 슬라이더를 각각 0으로 내려야 "꺼진 상태"가 된다.**
- **사용자 피드백 가설**: "환기 지금 다 끄고 싶은데 창문 0, 팬 0 따로 내려야 해서 번거롭다", "차광도 마찬가지. 원클릭으로 꺼지면 좋겠다." → 이를 해결한다.
- **하드웨어/서버 변경 금지**: 이 피처는 UX 완성도 개선이므로 ESP8266 펌웨어, Relay Server API, 데이터베이스, 인증 방식을 모두 변경하지 않는다. 모든 작업은 React 프론트엔드 내부에서 완료된다.

### 1.3 Related Documents

- 선행 Plan: `FarmOS/docs/01-plan/features/iot-manual-control.plan.md`
- 선행 Design: `FarmOS/docs/02-design/features/iot-manual-control.design.md`
- 구현체: `FarmOS/frontend/src/modules/iot/ManualControlPanel.tsx`, `FarmOS/frontend/src/hooks/useManualControl.ts`, `FarmOS/frontend/src/types/index.ts`

---

## 2. Scope

### 2.1 In Scope

- [ ] `ManualControlPanel.tsx`의 `VentilationCard`에 ON/OFF 마스터 스위치 버튼 추가 (blue-500 accent)
- [ ] `ManualControlPanel.tsx`의 `ShadingCard`에 ON/OFF 마스터 스위치 버튼 추가 (emerald-500 accent)
- [ ] 버튼 UX는 `LightingCard`의 ON/OFF 버튼과 동일 (위치, 모양, 라벨 "ON"/"OFF", 토글 동작)
- [ ] ON 시 동작:
  - 환기: 기억된 `(window_open_pct, fan_speed)` 복원. 없으면 프리셋 `(100, 1500)` 사용. `led_on = true`
  - 차광: 기억된 `(shade_pct, insulation_pct)` 복원. 없으면 프리셋 `(50, 0)` 사용. `led_on = true`
- [ ] OFF 시 동작:
  - 환기: `window_open_pct = 0`, `fan_speed = 0`, `led_on = false`
  - 차광: `shade_pct = 0`, `insulation_pct = 0`, `led_on = false`
  - OFF 직전의 현재 슬라이더 값을 `lastKnownValues` ref에 저장 (복원용)
- [ ] `types/index.ts`의 `ManualControlState['ventilation']`과 `ManualControlState['shading']`에 `on: boolean` 필드 추가
- [ ] `useManualControl` 훅 내부에서 `lastKnownValues` ref를 관리하는 로직 추가 (또는 카드 컴포넌트 로컬 ref)
- [ ] `/control` API payload 스키마는 그대로 두되, 프론트엔드가 `on` 필드를 추가 전송하는 것은 허용 (서버 무시해도 무방)
- [ ] `simulateButton` 경로에서도 `on` 상태가 일관적으로 반영되어야 함 (시뮬 시 슬라이더 변화 → `on` 자동 갱신)

### 2.2 Out of Scope

- ESP8266 펌웨어 수정 (`*.ino` 파일 한 줄도 건드리지 않음)
- Relay Server (`iot_relay_server/`) 코드 수정
- `LightingCard`의 기존 ON/OFF 로직 수정 — **그대로 유지** (회귀 0건 목표)
- `IrrigationCard`에 별도 ON/OFF 버튼 추가 — 밸브 토글이 이미 ON/OFF 역할 수행
- 새로고침 후에도 유지되는 값 저장 (`localStorage`) — 이번 범위에서 제외. 세션 내 `useRef`만 사용
- 서버 상태(`control_state`)에 `last_on_values` 추가 — Relay 변경 불필요
- 4대 제어 모두에 적용되는 "Global All OFF" 버튼 — 별도 피처로 분리 가능
- AI Agent가 `on` 필드를 해석하거나 사용하는 로직 — AI Agent는 `active`만 참조

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | `VentilationCard` 상단(제목/LED/SourceBadge/LockButton 라인) 아래 또는 옆에 ON/OFF 토글 버튼을 렌더링한다. 위치/모양/텍스트는 `LightingCard`와 일치. 색상만 blue-500 accent. | High | Pending |
| FR-02 | `ShadingCard` 상단에 동일 패턴의 ON/OFF 토글 버튼을 렌더링한다. 색상 emerald-500 accent. | High | Pending |
| FR-03 | 환기 ON 클릭 시: `lastKnownValues.ventilation`이 존재하면 그 값 복원, 없으면 프리셋 `{ window_open_pct: 100, fan_speed: 1500 }` 복원. 추가로 `on: true`, `led_on: true`를 포함한 command를 전송한다. | High | Pending |
| FR-04 | 환기 OFF 클릭 시: 현재 값 `{ window_open_pct, fan_speed }`를 `lastKnownValues.ventilation`에 ref 저장. 이어서 `{ window_open_pct: 0, fan_speed: 0, on: false, led_on: false }` command 전송. | High | Pending |
| FR-05 | 차광 ON 클릭 시: `lastKnownValues.shading`이 존재하면 그 값 복원, 없으면 프리셋 `{ shade_pct: 50, insulation_pct: 0 }` 복원. 추가로 `on: true`, `led_on: true`를 포함한 command 전송. | High | Pending |
| FR-06 | 차광 OFF 클릭 시: 현재 값 `{ shade_pct, insulation_pct }`를 `lastKnownValues.shading`에 ref 저장. 이어서 `{ shade_pct: 0, insulation_pct: 0, on: false, led_on: false }` command 전송. | High | Pending |
| FR-07 | `types/index.ts`에서 `ManualControlState['ventilation']`에 `on: boolean` 필드를 추가하고, `ManualControlState['shading']`에도 동일 필드를 추가한다. 기본값은 서버에서 받은 값 우선, 없으면 슬라이더가 0이 아닌 순간 `true`로 유추. | High | Pending |
| FR-08 | 기존 `active: boolean` 필드는 **그대로 유지**하며 ESP8266 하드웨어 버튼 상태를 나타내는 역할을 계속 수행한다. `on`과 `active`는 독립적으로 관리된다. | High | Pending |
| FR-09 | `useManualControl` 훅 내에서 `lastKnownValues` ref (또는 동등한 세션 스토리지)를 관리하고, 카드 컴포넌트에 `onMasterToggle(controlType)` 핸들러를 노출한다. | High | Pending |
| FR-10 | `simulateButton` 또는 수동 슬라이더 조작으로 슬라이더 값이 변경될 때 `on` 상태는 일관적으로 갱신된다 (예: 모든 슬라이더가 0이면 `on = false`, 하나라도 > 0이면 `on = true`). | Medium | Pending |
| FR-11 | ON/OFF 버튼은 카드가 `locked` 상태일 때 기존 LockButton의 UX 규칙을 그대로 따른다 (추가 제약 필요 시 Design 단계에서 결정). | Medium | Pending |
| FR-12 | `LightingCard`와 `IrrigationCard`의 기존 UX/로직은 변경되지 않는다 (코드 diff 최소화). | High | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Performance | 버튼 클릭 → UI 반영 < 50ms (로컬 상태) | React DevTools Profiler |
| Latency | 버튼 클릭 → Relay Server 반영 < 1초 (`sendCommandImmediate` 경로) | Network tab, SSE 이벤트 확인 |
| Regression | 조명/관수 카드 기능 회귀 0건 | 수동 checklist + E2E 시나리오 |
| Type Safety | `tsc --noEmit` 에러 0건 | `npm run typecheck` |
| Accessibility | 버튼 focus outline, aria-pressed 속성 적용 | 키보드 Tab 네비게이션 테스트 |
| Code Size | 순수 증분 코드 < 120 lines (types 포함) | git diff --stat |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] **SC-1**: `VentilationCard`에 조명 카드와 동일한 시각 패턴의 ON/OFF 버튼이 존재하며 clicking 시 타입 에러 없이 동작한다.
- [ ] **SC-2**: `ShadingCard`에 동일 패턴의 ON/OFF 버튼이 존재한다.
- [ ] **SC-3**: 환기 OFF 클릭 → 1초 내 `window_open_pct = 0`, `fan_speed = 0`, `led_on = false`가 UI와 Relay Server `/control/state`에 반영된다.
- [ ] **SC-4**: 차광 OFF 클릭 → 1초 내 `shade_pct = 0`, `insulation_pct = 0`, `led_on = false`가 UI와 서버에 반영된다.
- [ ] **SC-5**: 환기/차광을 OFF 한 뒤 ON 클릭 시 OFF 직전 슬라이더 값이 복원된다 (최초 진입 시에는 프리셋 `ventilation: (100, 1500)`, `shading: (50, 0)` 사용).

### 4.2 Quality Criteria

- [ ] `tsc --noEmit` 오류 0건
- [ ] `npm run build` 성공
- [ ] 기존 `LightingCard`/`IrrigationCard` UX 회귀 0건 (수동 checklist 통과)
- [ ] ESP8266 펌웨어 diff = 0, Relay Server diff = 0 (범위 외 변경 없음 확인)
- [ ] `on`과 `active`의 의미가 `types/index.ts` 주석 또는 Design 문서에 명시되어 개발자 혼동 방지

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `on` 필드와 기존 `active` 필드의 의미가 혼동되어 버그 유발 | High | Medium | `types/index.ts`에 JSDoc 주석으로 명확히 구분 (`on`: 프론트엔드 UX 마스터 스위치 / `active`: ESP8266 하드웨어 버튼 상태). Design 문서에 의미 차이 표로 정리. |
| `lastKnownValues` ref가 세션 내에만 존재하여 새로고침 시 사용자 혼란 | Medium | Medium | 최초 ON 시 프리셋 값을 사용함을 **UX 텍스트 또는 tooltip**으로 안내. 필요 시 차기 피처에서 localStorage 도입. |
| `simulateButton` 경로와 수동 ON/OFF 경로의 상태 불일치 | Medium | Medium | `useManualControl` 훅의 단일 상태 업데이트 경로 재사용 (`sendCommandImmediate`). 로컬 `on` 계산 로직을 파생 상태(derived)로 통일. |
| Relay Server가 `on` 필드를 인식하지 못해 SSE로 되돌아온 상태에 `on` 이 빠짐 | Low | Medium | 서버 응답 수신 시 `on`을 슬라이더 값에서 파생 계산 (any slider > 0 ⇒ on = true). 즉, `on` 은 "클라이언트 측 파생 + 사용자 의도 플래그"로 동작. |
| 마스터 OFF → ON 복원 시 ESP8266 LED가 이전 상태로 돌아오는 데 폴링 지연 | Low | High | 기존 폴링 2~3초 지연은 그대로 수용. UI에는 즉시 반영, ESP8266은 다음 폴링 주기에 동기화되는 것이 이미 선행 피처의 수용 기준. |
| 조명 카드 `on` 로직 재정리 욕구로 인한 스코프 크립 | Low | Low | **OOS 명시**. LightingCard 코드는 이번 PR에서 diff 0 라인 유지. PR review에서 확인. |
| `locked` 상태와 ON/OFF 버튼의 상호작용 미정의 | Medium | Medium | Design 단계에서 명시 결정 (안: locked 시 ON/OFF 버튼 비활성화 또는 tooltip "잠금 해제 후 사용"). |

---

## 6. Impact Analysis

### 6.1 Changed Resources

| Resource | Type | Change Description |
|----------|------|--------------------|
| `FarmOS/frontend/src/types/index.ts` | TypeScript Interface | `ManualControlState['ventilation']`, `ManualControlState['shading']`에 `on: boolean` 추가 |
| `FarmOS/frontend/src/modules/iot/ManualControlPanel.tsx` | React Component | `VentilationCard`, `ShadingCard` 내부에 ON/OFF 버튼 JSX 추가 + 핸들러 연결 |
| `FarmOS/frontend/src/hooks/useManualControl.ts` | React Hook | `lastKnownValues` ref + `onMasterToggle` 핸들러 추가 (또는 카드 로컬화 — Design에서 결정) |

### 6.2 Current Consumers

| Resource | Operation | Code Path | Impact |
|----------|-----------|-----------|--------|
| `ManualControlState` 타입 | READ | `ManualControlPanel.tsx`, `useManualControl.ts`, 기타 훅 | 기존 필드는 불변 → 필드 추가만이므로 **Non-breaking** |
| `VentilationCard` props | READ | `ManualControlPanel` 최상위 | Props 시그니처 변경 가능 (onButton → onMasterToggle 추가). 동일 부모 컴포넌트에서만 사용되므로 영향 제한적 |
| `ShadingCard` props | READ | `ManualControlPanel` 최상위 | 동일 |
| Relay Server `/control` POST | WRITE | `useManualControl.ts` → `sendCommand`/`sendCommandImmediate` | Body에 `on` 필드 추가. 서버 무시 무방(Q1 확인) → **Non-breaking** |
| SSE `control` 이벤트 | READ | `useSensorData.ts` → `onControlEvent` | 서버가 `on`을 echo-back 하지 않아도 로컬 파생 계산으로 대응 → **Non-breaking** |

### 6.3 Verification

- [ ] 조명 카드 ON/OFF 토글 동작이 변경 전과 동일 (시각 + API payload)
- [ ] 관수 카드 밸브 토글 동작이 변경 전과 동일
- [ ] Relay Server 응답 body에 `on`이 없어도 UI가 올바른 상태 표시
- [ ] `tsc --noEmit` 통과
- [ ] `ManualControlState`를 소비하는 다른 컴포넌트가 컴파일 에러 없이 동작

---

## 7. Architecture Considerations

### 7.1 Project Level Selection

| Level | Characteristics | Recommended For | Selected |
|-------|-----------------|-----------------|:--------:|
| **Starter** | Simple structure | Static sites, portfolios | - |
| **Dynamic** | Feature-based modules, BaaS integration | Web apps with backend, SaaS MVPs | **Selected** |
| **Enterprise** | Strict layer separation, microservices | High-traffic systems | - |

(선행 `iot-manual-control` 피처와 동일 Level 유지)

### 7.2 Key Architectural Decisions (Confirmed in Checkpoint 2)

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| 이전 슬라이더 값 저장 위치 | (a) React ref / (b) localStorage / (c) 서버 state 확장 | **(a) React ref** | Q2-1 확정. 세션 내 UX만 요구. 구현 최소, Relay 변경 불필요. 새로고침 시 프리셋 복귀는 수용 가능. |
| 환기 OFF 시 fan_speed | (a) window/fan 모두 0 / (b) window만 0 | **(a) 모두 0** | Q2-2 확정. "완전 OFF" 의미를 명확히. |
| 차광 OFF 시 shade/insulation | (a) 둘 다 0 / (b) 마지막 액티브만 0 | **(a) 둘 다 0** | Q2-3 확정. 카드 전체 OFF 의미의 일관성. |
| 타입 필드 전략 | (a) `on` 추가 / (b) `active` 재활용 | **(a) `on` 추가** | Q2-4 확정. ESP8266 하드웨어 버튼 상태(`active`)와 프론트엔드 UX 마스터 스위치(`on`)의 책임 분리. |
| 이전 값 복원 의미 | 최후 non-zero / OFF 직전 값 그대로 | **OFF 직전 값 그대로**, 없으면 프리셋 | Q1 추가 확인. `ventilation` 프리셋 = (window 100, fan 1500), `shading` 프리셋 = (shade 50, insulation 0). |
| `on` 파생 규칙 | 순수 상태 / 슬라이더 파생 | **사용자 의도 플래그 + 파생 fallback** | 사용자가 ON/OFF를 명시적으로 누르면 그 값. 서버 echo-back에 `on`이 없으면 `any slider > 0` 으로 파생. |

### 7.3 Clean Architecture Approach

```
Selected Level: Dynamic

변경 범위 (Frontend 전용):
┌────────────────────────────────────────────────────────────────────┐
│ Presentation Layer                                                │
│   src/modules/iot/ManualControlPanel.tsx                          │
│     - VentilationCard: +ON/OFF 버튼 JSX                            │
│     - ShadingCard   : +ON/OFF 버튼 JSX                             │
│                                                                   │
│ Application/Hook Layer                                            │
│   src/hooks/useManualControl.ts                                   │
│     - +lastKnownValues ref                                        │
│     - +onMasterToggle(controlType, nextOn) 핸들러                 │
│                                                                   │
│ Types Layer                                                       │
│   src/types/index.ts                                              │
│     - +on: boolean (ventilation, shading)                          │
│                                                                   │
│ 변경 없음: ESP8266 펌웨어, Relay Server API, Backend 전체           │
└────────────────────────────────────────────────────────────────────┘
```

---

## 8. Dependencies

### 8.1 Upstream Dependencies

- `iot-manual-control` Plan/Design/구현 완료 (4대 제어 카드 + `/control` API + `useManualControl` 훅)
- `FarmOS/frontend/src/types/index.ts` 내 `ManualControlState` 타입 존재
- `FarmOS/frontend/src/modules/iot/ManualControlPanel.tsx` 내 `LightingCard`가 참조 패턴 제공

### 8.2 Downstream Impact

- 없음 (이번 피처 이후 별도 피처가 `on` 필드를 활용할 수는 있으나 강제 의존 없음)

### 8.3 External Dependencies

- 실행 중인 Relay Server (`iot.lilpa.moe:9000`) — 기존 그대로 사용
- 실행 중인 ESP8266 디바이스 또는 `simulateButton` — 기존 그대로 사용

### 8.4 Environment Variables

| Variable | Purpose | Scope | Change |
|----------|---------|-------|:------:|
| `VITE_IOT_API_URL` | Relay Server URL | Frontend | No change |
| `IOT_API_KEY` | ESP8266 인증 | Relay Server | No change |

---

## 9. Timeline / Milestones

Dynamic level 간소화 기준으로 단일 세션 완료를 목표로 한다.

| Milestone | Deliverable | Owner | Target |
|-----------|-------------|-------|--------|
| M1 Design Approval | Design 문서 Architecture Option 선택 완료 | CTO Lead | Session 1 |
| M2 Implementation | `types` + `useManualControl` + `ManualControlPanel` 3파일 수정 | Developer | Session 1~2 |
| M3 Smoke Test | 환기/차광 OFF→ON 복원, 조명/관수 회귀 없음 수동 확인 | QA | Session 2 |
| M4 Check (Gap Analysis) | Match Rate ≥ 90% | gap-detector | Session 2 |
| M5 Report | 완료 보고서 | CTO Lead | Session 2 |

> **메모**: 본 피처는 Minor~Feature 규모(코드 증분 < 120 lines 예상)이므로 Agent Teams swarm 없이 CTO Lead leader 패턴으로 충분하다.

---

## 10. Open Questions

| ID | Question | Status |
|----|----------|:------:|
| OQ-1 | `locked` 상태에서 ON/OFF 버튼을 비활성화할지 / 잠금 해제 프롬프트를 띄울지 | Deferred to Design Phase |
| OQ-2 | ON/OFF 버튼 위치: 카드 상단 헤더 라인에 통합할지 / 별도 라인으로 분리할지 | Deferred to Design Phase |
| OQ-3 | `simulateButton`이 슬라이더를 0으로 만들었을 때 `on`이 자동으로 `false`가 되어야 하는지 (derived) / 사용자 명시 의도로만 변경되어야 하는지 | Deferred to Design Phase |

> 주요 요구사항(복원값 저장소, OFF 동작, 타입 설계)은 Checkpoint 2에서 모두 확정. 상기 OQ는 모두 **구현 세부/UX 폴리시**로 Design 단계에서 해결 가능.

---

## 11. Convention Prerequisites

### 11.1 Existing Project Conventions

- [x] TypeScript strict mode (Frontend)
- [x] React functional components + hooks pattern
- [x] `useRef`를 통한 세션 상태 관리 (`useManualControl` 내 `ControlSlider` 참고)
- [x] Tailwind accent class 규칙 (`accent-blue-500`, `accent-emerald-500` 등 `ACCENT_CLASSES` 매핑)
- [x] LED/Source/Lock indicator 컴포넌트 재사용 패턴

### 11.2 New Conventions to Introduce

| Convention | Description |
|------------|-------------|
| `on` vs `active` 명명 | `on` = 프론트엔드 UX 마스터 스위치 (사용자 의도 + 슬라이더 파생), `active` = ESP8266 하드웨어 버튼 상태 (서버 echo-back). `types/index.ts` JSDoc 주석으로 명시. |
| 프리셋 상수 | `src/hooks/useManualControl.ts` 또는 `src/constants/manualControl.ts`에 `VENTILATION_ON_PRESET = { window_open_pct: 100, fan_speed: 1500 }`, `SHADING_ON_PRESET = { shade_pct: 50, insulation_pct: 0 }` 상수로 분리 (하드코딩 방지) |

---

## 12. Next Steps

1. [ ] Design 문서 작성 (`manual-control-onoff.design.md`) — 3 architecture options 제시 (Minimal / Clean / Pragmatic)
2. [ ] Checkpoint 3 (Architecture Selection) 사용자 선택 수신
3. [ ] Implementation 세션 진입 (`/pdca do manual-control-onoff`)
4. [ ] Gap analysis (`/pdca analyze manual-control-onoff`)
5. [ ] Report + archive

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-21 | Initial draft (Checkpoint 1+2 확정 반영) | clover0309 via CTO Lead |
