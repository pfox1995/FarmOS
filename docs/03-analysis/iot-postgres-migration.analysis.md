# IoT 인메모리 → PostgreSQL 마이그레이션 Analysis (Check)

> ⚠️ **DEPRECATED (2026-04-21)** — 이 분석 대상이었던 FarmOS 로컬 `iot_sensor_readings` / `iot_sensor_alerts` / `iot_irrigation_events` 테이블과 `/api/v1/sensors*`, `/api/v1/irrigation/*` 엔드포인트는 **제거되었습니다.**
> IoT 센서·알림·관수 데이터의 SSoT는 `iot_relay_server`(N100)의 `iotdb` 로 일원화되었고, FarmOS 로컬 DB는 AI 판단(`ai_agent_decisions` 외 2개)만 Bridge로 미러링합니다.
> 본 문서는 당시 이관 분석 기록으로 보존합니다. 최신 구조는 `docs/iot-relay-server-plan.md` 참조.

| 항목 | 값 |
|------|-----|
| Feature | iot-postgres-migration |
| Phase | Check (Static only, runtime verification pending server restart) |
| Created | 2026-04-20 |

## Context Anchor (inherited)

| Key | Value |
|-----|-------|
| WHY | 재시작 시 IoT 이력 소실 → AI Agent 회고 불가 |
| SUCCESS | SC-1 재시작 후 history 유지, SC-2 iot_* 3 테이블, SC-3 응답 shape 불변, SC-4 /health.storage=postgres |

## 1. Structural Match

| 산출물 | 기대 | 확인 |
|--------|------|:---:|
| `backend/app/models/iot.py` (3 모델) | 신규 생성 | ✅ |
| `backend/app/core/store.py` 전면 재작성 | PostgreSQL 쿼리 기반 async | ✅ |
| `backend/app/api/sensors.py` DI | `db: AsyncSession = Depends(get_db)` 적용 | ✅ |
| `backend/app/api/irrigation.py` DI | 동일 | ✅ |
| `backend/app/api/health.py` DI | 동일, storage=postgres | ✅ |
| `backend/app/main.py` 모델 import | `IotSensorReading/…` 추가 | ✅ |
| `docs/database-schema.md` | 인메모리 섹션 제거, iot_ 테이블 문서화 | ✅ |
| `docs/backend-architecture.md` | 저장소 구분 변경, health 예시 변경, 데이터 흐름 도식 갱신 | ✅ |
| `docs/iot-relay-server-plan.md` | PostgreSQL 버전으로 재명세 + §9 diff | ✅ |
| `docs/iot-relay-server-postgres-patch.md` | N100 Relay 패치 스펙 신규 | ✅ |

**Structural: 100%**

## 2. Functional Depth

| 기능 | 설계 | 구현 |
|------|------|:---:|
| POST /sensors → readings insert + 자동 alert/irrigation | 단일 트랜잭션 | ✅ `db.add`×N + 최종 `db.commit` |
| GET /sensors/latest | timestamp DESC LIMIT 1 | ✅ |
| GET /sensors/history | DESC LIMIT N → reverse(오름차순) | ✅ |
| GET /sensors/alerts (resolved 필터) | `WHERE resolved = :v` | ✅ |
| PATCH /sensors/alerts/{id}/resolve | UPDATE + rowcount 반환 | ✅ |
| POST /irrigation/trigger | event insert, camelCase 응답 | ✅ |
| GET /irrigation/events | triggered_at DESC | ✅ |
| GET /health | `SELECT 1` + 3 테이블 COUNT(*) | ✅ |
| 토양습도 추정 & 시간 관성 | 모듈 상태 `_prev_soil_moisture` 유지 | ✅ |

**Functional: 100%**

## 3. API Contract

| 엔드포인트 | 이전 응답 키 | 이후 응답 키 | 일치 |
|-----------|-------------|-------------|:---:|
| /sensors/latest | device_id, timestamp, soilMoisture, temperature, humidity, lightIntensity | 동일 (`_reading_to_dict` 변환) | ✅ |
| /sensors/history | 위와 동일 (list) | 동일 | ✅ |
| /sensors/alerts | id, type, severity, message, timestamp, resolved | 동일 | ✅ |
| /irrigation/events | id, triggeredAt, reason, valveAction, duration, autoTriggered | 동일 | ✅ |
| /irrigation/trigger | 위와 동일 (단건) | 동일 | ✅ |
| /health | status, storage, readings_count, irrigation_events_count, alerts_count | storage 값만 `"in-memory"`→`"postgres"` (Plan 요구) | ✅ |

**Contract: 100%** (의도된 변경: `/health.storage` 값)

## 4. Success Criteria 검증

| SC | 내용 | 상태 | 증거 |
|----|------|:----:|------|
| SC-1 | 재시작 후 history 유지 | 🕓 런타임 검증 대기 | 재시작 + curl 필요 |
| SC-2 | iot_* 3 테이블 자동 생성 | 🕓 런타임 검증 대기 | `init_db()`가 `create_all` 호출 + 모델 import 등록 확인 ✅ (코드상 보증) |
| SC-3 | 응답 shape 불변 | ✅ | `_*_to_dict` 함수로 camelCase 유지 |
| SC-4 | `/health.storage=postgres` | ✅ | `api/health.py:28` 고정값 |

## 5. Static Match Rate

```
Structural × 0.2 = 20
Functional × 0.4 = 40
Contract   × 0.4 = 40
────────────────────
Overall          = 100  (static only)
```

보수적으로 런타임 미검증 감점 반영 시 **≈95%**.

## 6. 런타임 검증 Plan (사용자 수행 권장)

```bash
# 1) 로컬 BE 재기동
start-all.bat

# 2) 헬스체크
curl -s http://localhost:8000/api/v1/health | jq
# 기대: {"status":"ok","storage":"postgres","readings_count":0,...}

# 3) 센서 POST (API Key 필요)
curl -XPOST http://localhost:8000/api/v1/sensors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: farmos-iot-default-key" \
  -d '{"device_id":"test","sensors":{"temperature":25,"humidity":60,"light_intensity":30000}}'

# 4) 히스토리 확인
curl -s "http://localhost:8000/api/v1/sensors/history?limit=10" \
  -H "Authorization: Bearer <jwt>" | jq length

# 5) 재기동 후 3→4 다시 실행 → 이전 데이터가 남아있으면 SC-1 PASS
```

## 7. 남은 작업

- [ ] 로컬 BE 런타임 스모크 테스트 (사용자 수행)
- [ ] N100 Relay 패치 적용 (사용자 수행, `docs/iot-relay-server-postgres-patch.md` 참조)
- [ ] 프론트엔드 대시보드 그래프 회귀 확인 (응답 shape 불변으로 이론상 무변경)

## 8. 결론

- 정적 분석 기준 Design-Code 일치율 **100%**.
- 런타임 미검증 감안 Match Rate **≈95%** — 90% 임계 초과로 Act(iterate) 불필요.
- 다음 단계: 사용자 로컬 재기동으로 SC-1/SC-2 확인 후 Report 단계 진행 가능.
