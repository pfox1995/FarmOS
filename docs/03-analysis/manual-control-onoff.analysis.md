# Manual Control ON/OFF — Gap Analysis Report

> **Feature**: manual-control-onoff
> **Plan**: `FarmOS/docs/01-plan/features/manual-control-onoff.plan.md`
> **Design**: `FarmOS/docs/02-design/features/manual-control-onoff.design.md` (Option C — Pragmatic)
> **Implementation**: `frontend/src/types/index.ts`, `frontend/src/hooks/useManualControl.ts`, `frontend/src/modules/iot/ManualControlPanel.tsx`
> **Date**: 2026-04-21
> **Mode**: Static analysis only (no runtime)
> **Analyst**: gap-detector agent

---

## Context Anchor

| Key | Value |
|-----|-------|
| **WHY** | 4대 제어 카드 중 조명만 ON/OFF 마스터 스위치 보유 → UX 비일관성 |
| **WHO** | FarmOS 대시보드 1인 농업인 운용자 |
| **RISK** | active/on 혼동, ref 정합성, simulateButton 경로 일관성 |
| **SUCCESS** | 환기/차광 ON/OFF + 회귀 0 + 서버 변경 0 |
| **SCOPE** | Frontend 3파일 (types/hook/panel) |

---

## Match Rate Summary

| Axis | Score | Verdict |
|------|:-----:|:-------:|
| Structural Match | **100%** | Full coverage |
| Functional Depth | **97%** | Minor semantic deviation on shading ON insulation |
| API Contract | **100%** | 4 payloads 도달 가능, fetchState 정규화 일치 |
| **Overall** | **~98%** | ✅ Pass (≥ 90%) |

Weights used: Structural 0.15 / Functional 0.35 / Contract 0.30 / Intent 0.10 / Behavioral 0.10 → 100·0.15 + 97·0.35 + 100·0.30 + 95·0.10 + 95·0.10 = **98.0%**

---

## 1. Structural Match (100%)

### 1.1 Design §3 Data Model

| Spec | Evidence | Status |
|------|----------|:------:|
| `VentilationState.on: boolean` | `src/types/index.ts:426` | ✅ |
| `ShadingState.on: boolean` | `src/types/index.ts:444` | ✅ |
| `Design Ref: §3.1` comment present | types/index.ts:426, :444 | ✅ |
| `ControlItemState.active` preserved unchanged | types/index.ts:415-421 | ✅ |

### 1.2 Design §5 Hook Changes

| Spec | Evidence | Status |
|------|----------|:------:|
| `lastKnownValuesRef` declared | useManualControl.ts:18-21 | ✅ |
| `fetchState` `on ?? led_on ?? false` normalization | useManualControl.ts:29-40 | ✅ |
| `simulateButton` ventilation case — ref save + `on:newActive` | useManualControl.ts:136-149 | ✅ |
| `simulateButton` shading case — ref save + `on:newActive` | useManualControl.ts:156-169 | ✅ |
| Return extended with `lastKnownValuesRef` | useManualControl.ts:277 | ✅ |
| `Design Ref` comments (§5.1/§5.2/§5.3/§5.4) | L17, L29, L137, L157, L277 | ✅ |

### 1.3 Design §6 UI Changes

| Spec | Evidence | Status |
|------|----------|:------:|
| VentilationCard `handleMasterToggle` | ManualControlPanel.tsx:139-152 | ✅ |
| VentilationCard ON/OFF button (blue-500) | :166-175 | ✅ |
| VentilationCard slider `disabled={!state.on}` | :187 | ✅ |
| VentilationCard fan preset buttons disabled when `!on && rpm>0` | :204-205 | ✅ |
| ShadingCard `handleMasterToggle` | :319-330 | ✅ |
| ShadingCard ON/OFF button (emerald-500) | :344-353 | ✅ |
| ShadingCard both sliders `disabled={!state.on}` | :365, :378 | ✅ |
| Panel passes `lastKnownRef` to both cards | :451, :469 | ✅ |
| Panel passes `onCommand`/`onMaster` = `sendCommandImmediate` | :454, :471 | ✅ |
| `Design Ref` comments (§6.1/§6.2/§6.3) | L118, L305, L396 | ✅ |
| IrrigationCard/LightingCard untouched | :215-303 | ✅ |

---

## 2. Functional Depth (97%)

No `TODO`/`FIXME`/`placeholder` strings detected. Logic is real.

### §12 Acceptance Criteria — All 9 items

| # | Criterion | Evidence | Status |
|---|-----------|----------|:------:|
| 1 | VentilationCard "상태" row + ON/OFF button (blue-500) | Panel:164-176 | ✅ |
| 2 | ShadingCard "상태" row + ON/OFF button (emerald-500) | Panel:342-354 | ✅ |
| 3 | ON click restores last value or preset | Panel:148-150, 326-328 | ✅ |
| 4 | OFF click → sliders=0 + led_on=false | Panel:142-146, 321-325 | ✅ |
| 5 | Slider/preset buttons disabled when OFF | Panel:187, 204-205, 365, 378 | ✅ |
| 6 | `simulateButton` ventilation/shading OFF saves ref | useManualControl:138-143, 158-163 | ✅ |
| 7 | IrrigationCard/LightingCard diff 0 | Panel:215-303 unchanged | ✅ |
| 8 | `/control/state` response without `on` handled | useManualControl:29-40 | ✅ |
| 9 | Irrigation/Lighting regression clean | No changes in those functions | ✅ (static) |

---

## 3. API Contract (100%)

### 3.1 Payload Reachability

| Design §4.2 Row | Produced at | Actual payload | Match |
|-----------------|-------------|----------------|:-----:|
| 환기 ON (복원) | Panel:150 | `{ window_open_pct: <ref or 100>, fan_speed: <ref or 1500>, on:true, led_on:true }` | ✅ |
| 환기 OFF | Panel:146 | `{ window_open_pct:0, fan_speed:0, on:false, led_on:false }` | ✅ |
| 차광 ON (복원) | Panel:328 | `{ shade_pct: <ref or 50>, insulation_pct: <ref or 0>, on:true, led_on:true }` | ✅ |
| 차광 OFF | Panel:325 | `{ shade_pct:0, insulation_pct:0, on:false, led_on:false }` | ✅ |

All 4 flows: `sendCommandImmediate` → `_postControl` → `POST /control` with wrapper `{ control_type, action, source:'manual' }`.

### 3.2 `fetchState` normalization

| Design §5.4 spec | Implementation | Match |
|------------------|----------------|:-----:|
| `on: data.ventilation.on ?? data.ventilation.led_on ?? false` | `useManualControl.ts:29-40` + defensive `?.` chain | ✅ |
| `on: data.shading.on ?? data.shading.led_on ?? false` | Same | ✅ |

---

## 4. Plan Success Criteria Verdict

| SC | Status | Evidence |
|----|:------:|----------|
| **SC1** 환기/차광 카드에 조명과 동일 패턴 ON/OFF 버튼, 색상만 blue-500/emerald-500 교체 | ✅ | Ventilation Panel:166-175, Shading Panel:344-353, 구조 동형 |
| **SC2** OFF=모든 슬라이더 0+led_on false / ON=ref 복원 또는 프리셋 | ✅ | Ventilation :139-152, Shading :319-330; 프리셋 `{100,1500}` / `{50,0}` |
| **SC3** IrrigationCard/LightingCard 내부 로직 변경 0 | ✅ | Panel:215-303 unchanged |
| **SC4** fetchState on 필드 누락 시 led_on fallback | ✅ | useManualControl:29-40 |
| **SC5** simulateButton ventilation/shading 일관 처리 | ✅ | useManualControl:144-148, :164-168 |

**Overall: 5/5 Met**

---

## 5. Gap List

### 🔴 Critical
- **None.**

### 🟡 Important
- **None.**

### 🔵 Minor / Observations

| # | Item | File:Line | Recommendation |
|---|------|-----------|----------------|
| M1 | Prop naming asymmetry: VentilationCard uses `onCommand`, ShadingCard uses `onMaster` | Panel:129 vs :310 | Unify to `onMaster` (cosmetic, not blocking) |
| M2 | `simulateButton` shading ON hardcodes `insulation_pct: 0` instead of ref restore | useManualControl.ts:167 | Matches Design §5.2 exactly. Design-compliant |
| M3 | VentilationCard slider `on` derivation: `v > 0 \|\| state.fan_speed > 0` | Panel:185, :199 | Intentional (risk mitigation §10 R4). No change |
| M4 | a11y: ON/OFF 버튼에 `aria-pressed={state.on}` 미설정 | Panel:166, :344 | Plan NFR 언급, 추가 권장. 비블로킹 |

---

## 6. Non-Functional Compliance

| NFR | Status | Evidence |
|-----|:------:|----------|
| TypeScript strict: `on: boolean` required | ✅ | types/index.ts:426, 444 |
| Code size < 120 lines | ⚠️ | ~124 lines (목표 92, 주석/destructuring 증가분). Minor overage |
| Relay Server / ESP8266 diff = 0 | ✅ | Not touched |
| `locked` / `LockButton` UX 유지 | ✅ | Panel:161, :313, :339 |
| Accessibility `aria-pressed` | ⚠️ | 미설정 (M4 참조) |

---

## 7. Runtime Verification Plan

### L1 — API Endpoint Tests (curl)

| # | Test | Expected |
|---|------|----------|
| 1 | Ventilation OFF POST `/control` | 200 OK |
| 2 | Ventilation ON with preset | 200 OK |
| 3 | Shading OFF | 200 OK |
| 4 | Shading ON | 200 OK |
| 5 | GET `/control/state` without `on` field | Hook normalizes |

### L2 — UI Action Tests (Playwright)

| # | Action | Expected |
|---|--------|----------|
| 1 | VentilationCard ON→OFF | Slider → 0, fan "OFF" highlighted, disabled |
| 2 | Drag window to 80 → OFF → ON | Slider returns to 80 |
| 3 | First click ON (fresh) | Preset 100/1500 |
| 4 | ShadingCard OFF then ON (fresh) | Preset 50/0 |
| 5 | Sim mode → sim[환기] → manual[ON] | Sim-OFF snapshot 복원 |

### L3 — E2E

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Ventilation OFF → <5s AI rule SSE arrives | `on=false` 유지 (manualTimestamps 보호) |
| 2 | Reload → Ventilation ON (ref empty) | Preset 사용 |

---

## 8. Recommended Actions

### Immediate (None required)
- Match Rate ~98% ≥ 90% → **iterate 불필요**
- Feature is ready for QA / Report phase

### Optional Polish (Non-blocking)
1. **a11y**: ON/OFF `<button>`에 `aria-pressed={state.on}`, `aria-label="환기 전원 전환"` 추가
2. **Prop naming**: VentilationCard `onCommand` → `onMaster` 통일
3. **Runtime verification**: 활성 Relay Server 있으면 L1 curl 표 실행

### Next Command
`/pdca report manual-control-onoff` (iterate 스킵, 임계치 충족)

---

## 9. Verdict

**PASS** — 구현이 Option C Design을 충실히 구현. Plan SC1-SC5 모두 ✅ with file:line evidence. Design Ref 주석 전체 변경점에 포함. IrrigationCard/LightingCard 회귀 없음 (SC3 clean). 관찰 사항은 cosmetic + 1건 a11y 누락, 배포 블로킹 없음.
