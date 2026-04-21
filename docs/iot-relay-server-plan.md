# IoT 중계 서버 구축 계획 (N100 서버)

> **업데이트 이력**
> - 2026-04-21: FarmOS 로컬 DB의 레거시 IoT 테이블(`iot_sensor_readings` / `iot_sensor_alerts` / `iot_irrigation_events`)과
>   관련 엔드포인트(`/api/v1/sensors*`, `/api/v1/irrigation/*`) **완전 제거**. IoT 센서·알림·관수 데이터의
>   SSoT는 이제 Relay 전용 `iotdb` 단일 저장소이며, FarmOS DB는 AI 판단 미러(`ai_agent_decisions` 외 2개)만 보관한다.
>   제거 마이그레이션: `backend/scripts/drop_iot_legacy_tables.sql`. Relay 접근 없이는 IoT 기능 사용 불가.
> - 2026-04-20: 저장소를 인메모리(`deque`/`list`)에서 **PostgreSQL**로 변경.
>   Relay는 기존에 N100에서 돌던 다른 PostgreSQL 과 **격리된 전용 컨테이너(`iot-postgres`)** 를 운영한다.
>   30초 주기 INSERT 워크로드가 기존 DB 성능에 영향을 주지 않고 백업/업그레이드/리셋도 독립.

## 1. 배경 및 목적

ESP8266에서 센서 데이터를 수집하여 FarmOS 프론트엔드에 전달해야 한다.
로컬 PC 직접 통신은 네트워크 환경에 따라 불안정하고,
ngrok은 HTTPS만 지원하여 ESP8266의 TLS 메모리 한계로 연결이 실패한다.

**해결책**: 개인 N100 서버에 경량 중계 FastAPI 앱을 Docker로 배포.
ESP8266은 핫스팟을 통해 N100 서버에 HTTP로 직접 통신한다.
수신된 데이터는 **IoT 전용 PostgreSQL 컨테이너(`iot-postgres`)** 에 영속 저장된다(재시작해도 이력 유지).
기존에 N100에서 돌던 다른 Postgres 와는 네트워크/볼륨/자격증명이 완전히 분리된다.

---

## 2. 전체 아키텍처

```
┌──────────────┐        HTTP POST         ┌────────────────────────────────────┐
│   ESP8266    │ ───────────────────────→ │            N100 서버                │
│  (핫스팟)     │     :9000/api/v1/sensors │                                     │
│  DHT11+CdS   │                          │  ╔═══ iot_net (전용) ═══════════╗   │
└──────────────┘                          │  ║  ┌──────────────┐            ║   │
                                          │  ║  │ iot-relay    │            ║   │
                                          │  ║  │ FastAPI:9000 │──┐asyncpg  ║   │
                                          │  ║  └──────────────┘  ▼         ║   │
                                          │  ║  ┌──────────────────────┐   ║   │
                                          │  ║  │ iot-postgres (전용)   │   ║   │
                                          │  ║  │ iot_sensor_readings   │   ║   │
                                          │  ║  │ iot_irrigation_events │   ║   │
                                          │  ║  │ iot_sensor_alerts     │   ║   │
                                          │  ║  │ vol: iot_pgdata       │   ║   │
                                          │  ║  └──────────────────────┘   ║   │
                                          │  ╚═════════════════════════════╝   │
                                          │                                     │
                                          │  ┌──────────────────────┐           │
                                          │  │ (기존) 다른 Postgres  │  ← 완전 │
                                          │  │  포트폴리오 등 별용도 │   격리   │
                                          │  └──────────────────────┘           │
                                          │                                     │
                                          │  nginx (80/443) — 기존 유지          │
                                          └────────────────────────────────────┘
                                                    │
                                          GET /api/v1/sensors/*
                                                    │
                                          ┌──────────────────┐
                                          │   프론트엔드      │
                                          │   (개발 PC)       │
                                          │   localhost:5173  │
                                          └──────────────────┘
```

**포트 배분**:
- 80/443: nginx (포트폴리오 배포 - 기존 유지)
- 9000: IoT 중계 서버 (FastAPI)
- `iot-postgres`는 **외부 미노출** (전용 `iot_net` 내부에서만 Relay 가 접근). 디버깅 시 `127.0.0.1:5433` 바인딩 옵션만 열어둠.
- 기존 다른 PostgreSQL 과 네트워크/볼륨/자격증명 모두 분리.

---

## 3. 구현 위치

N100 프로젝트 루트의 `iot_relay_server/` 디렉토리:

```
iot_relay_server/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI 앱 (CORS, 라우터, asyncpg Pool lifespan)
│   ├── store.py          # PostgreSQL 저장소 (asyncpg)
│   ├── schemas.py        # Pydantic 검증 스키마
│   └── config.py         # 환경변수 (DATABASE_URL 포함)
├── Dockerfile
├── docker-compose.yml     # iot-relay + iot-postgres (전용, iot_net 네트워크)
├── requirements.txt       # asyncpg 추가
├── iot_init.sql           # 3 테이블 DDL (initdb 훅으로 최초 1회 자동 적용)
└── .env                   # PG_USER / PG_PASSWORD / PG_DB / IOT_API_KEY
```

> 구체 코드 패치와 DDL은 `docs/iot-relay-server-postgres-patch.md` 를 참조한다.

---

## 4. 주요 엔드포인트

| Method | Path | 인증 | 용도 |
|--------|------|------|------|
| POST | `/api/v1/sensors` | X-API-Key | ESP8266 데이터 수신 → `iot_sensor_readings` insert |
| GET | `/api/v1/sensors/latest` | 없음 | 최신 센서 값 1건 (timestamp DESC LIMIT 1) |
| GET | `/api/v1/sensors/history` | 없음 | 시계열 (limit 파라미터, timestamp DESC LIMIT N) |
| GET | `/api/v1/sensors/alerts` | 없음 | 알림 목록 (resolved 필터) |
| PATCH | `/api/v1/sensors/alerts/{id}/resolve` | 없음 | 알림 해결 처리 (UPDATE resolved=true) |
| POST | `/api/v1/irrigation/trigger` | 없음 | 수동 관개 제어 → `iot_irrigation_events` insert |
| GET | `/api/v1/irrigation/events` | 없음 | 관개 이벤트 이력 |
| GET | `/health` | 없음 | 헬스체크 (DB 연결 상태 + row count 포함) |

> GET 엔드포인트는 JWT 인증 없이 공개 (시연용).
> POST /sensors만 API Key로 보호.
> 응답 JSON shape(camelCase)은 기존 인메모리 버전과 동일 → 프론트 회귀 없음.

---

## 5. 배포 순서

| 단계 | 작업 | 확인 방법 |
|------|------|----------|
| 1 | N100에 `iot_relay_server/` 복사 (scp / git pull) | `ls iot_relay_server/` |
| 2 | `.env` 에 `PG_USER/PG_PASSWORD/PG_DB/IOT_API_KEY` 설정 | 파일 편집 |
| 3 | `iot_init.sql` 이 `iot_relay_server/` 에 있는지 확인 (initdb 훅으로 자동 적용됨) | `ls iot_init.sql` |
| 4 | `cd iot_relay_server && docker compose up -d --build` (iot-postgres 가 initdb 로 3 테이블 자동 생성) | `docker compose ps` |
| 5 | `docker compose logs iot-postgres \| grep "01-iot_init"` 로 initdb 실행 확인 | 로그 확인 |
| 6 | `docker compose exec iot-postgres psql -U iotuser -d iotdb -c "\dt iot_*"` | 3 테이블 확인 |
| 7 | `curl http://localhost:9000/health` → `{"storage":"postgres", ...}` | 응답 확인 |
| 8 | N100 방화벽에서 9000 포트 개방 | `curl http://N100_IP:9000/health` |
| 9 | ESP8266 `.ino`에 N100 공인 IP 설정 후 업로드 | 시리얼 모니터 `Server Say : 201` |
| 10 | 프론트엔드 `useSensorData.ts`의 API_BASE 변경 | IoT 대시보드에 실시간 데이터 표시 |
| 11 | Relay 재시작 후 `/sensors/history` 에 이전 데이터 포함 여부 확인 | 이력 영속성 검증 |

---

## 6. ESP8266 변경사항

```cpp
// .ino 파일에서 변경
const char* serverHost = "http://{N100_공인IP}:9000";
```

- WiFiClient (HTTP) 사용 — TLS 불필요
- ESP8266은 핫스팟으로 인터넷 연결
- PostgreSQL 전환 후에도 ESP8266 코드 변경 없음 (계약 불변)

---

## 7. 프론트엔드 변경사항

`frontend/src/hooks/useSensorData.ts`:

```typescript
// 변경 전
const API_BASE = 'http://localhost:8000/api/v1';

// 변경 후 (환경변수 분리 권장)
const API_BASE = import.meta.env.VITE_IOT_API_URL || 'http://localhost:8000/api/v1';
```

`.env` 또는 `.env.local`:
```
VITE_IOT_API_URL=http://{N100_공인IP}:9000/api/v1
```

> PostgreSQL 전환은 응답 JSON shape을 유지하므로 프론트엔드 코드 수정은 없다.

---

## 8. 보안 참고

- POST만 API Key 보호 (무단 데이터 삽입 방지)
- GET은 인증 없이 공개 (시연용)
- **PostgreSQL 컨테이너는 Docker 내부 네트워크 전용** — 외부 포트(5432) 노출 금지
- DB 자격증명은 `.env` 에만 보관, 리포지토리 커밋 금지
- CORS `allow_origins=["*"]` (시연 환경)
- 데이터는 PostgreSQL 볼륨에 영속 저장 → 컨테이너 재생성 후에도 유지

---

## 9. 이전 인메모리 버전과의 차이

| 항목 | 이전 (인메모리) | 이후 (PostgreSQL) |
|------|----------------|-------------------|
| 저장소 | `deque` (2000건) + `list` | `iot_sensor_readings` / `iot_irrigation_events` / `iot_sensor_alerts` |
| 영속성 | ✗ 재시작 시 소실 | ✓ 재시작·컨테이너 재생성 후에도 유지 |
| 보관 기간 | 최대 2000건 (약 16시간) | 무제한 (필요 시 파티셔닝/TTL 정책 추가) |
| `/health.storage` | `"in-memory"` | `"postgres"` |
| 의존성 | 없음 | `asyncpg` |
| AI Agent 이력 분석 | 제한적 (짧은 버퍼) | 장기 추세 분석 가능 |
