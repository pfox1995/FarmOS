# IoT Relay Server — PostgreSQL 전환 패치 스펙 (전용 컨테이너 분리)

> **목적**: N100의 `iot_relay_server/` 를 인메모리에서 **전용 PostgreSQL 컨테이너**로 전환.
> **적용**: 사용자가 N100 서버에서 직접 적용. 현재 리포는 `iot_relay_server/` 를 **루트 수준에서 포함**하고 있어 본 문서의 DDL/`app/store.py`/`app/main.py` 패치 구조와 1:1 매치됨.
> **설계 결정 (2026-04-20)**: 기존 운영 중인 PostgreSQL 과 **격리된 전용 컨테이너** 운영.
>   → 30초 주기 INSERT 워크로드가 기존 DB 성능에 영향을 주지 않음 + 독립 백업/업그레이드/리셋 가능.
>
> **Code Sync 2026-04-23 (Verification)**: §1 DDL (3 테이블 + `iot_agent_decisions` §10.1) 은 현재 Relay `iot_relay_server/iot_init.sql` 과 `app/store.py` asyncpg 쿼리에 그대로 적용되어 있음. §10.4 persist-before-broadcast 불변식은 `iot-ai-agent-implementation.md §13.2` 에 재정의되어 운영 규칙으로 격상됨. §10.8 asyncpg `AmbiguousParameterError` 대응(`CAST(:src AS text)`) 은 `backend/app/services/ai_agent_bridge.py` `_bump_daily` / `_bump_hourly` 에 반영 완료. 본 문서는 **현행 구조와 일치**하며 추가 수정이 필요하지 않다.

## 0. 아키텍처 (전용 컨테이너)

```
iot_relay_server/ (N100)  ──  docker compose 파일 1개로 관리
│
├─ iot-relay       (:9000)     FastAPI, asyncpg Pool
│       │ DSN: postgresql+asyncpg://iotuser:***@iot-postgres:5432/iotdb
│       ▼
├─ iot-postgres    (포트 미노출 or 5433)
│       │ volume: iot_pgdata
│       │ initdb: /docker-entrypoint-initdb.d/iot_init.sql
│
└─ network: iot_net (internal, 기존 다른 PG 와 분리)
```

- 기존 PostgreSQL 컨테이너와 **완전히 독립**. 네트워크/볼륨/자격증명 모두 별개.
- 호스트 포트는 기본 **미노출** (보안). 필요 시 `5433:5432` 로 외부 접근 허용.
- DB/테이블은 **최초 기동 시 자동 생성** (Postgres 공식 이미지의 `docker-entrypoint-initdb.d` 규칙 사용).

---

## 0-A. 체크리스트

- [ ] `iot_relay_server/iot_init.sql` 파일 추가 (3 테이블 DDL)
- [ ] `iot_relay_server/docker-compose.yml` 에 `iot-postgres` 서비스 추가
- [ ] `iot_relay_server/.env` 에 `PG_USER/PG_PASSWORD/PG_DB` 추가
- [ ] `requirements.txt` 에 `asyncpg` 추가
- [ ] `app/store.py` 교체 (§3)
- [ ] `app/main.py` lifespan 수정 (§4)
- [ ] `app/api/*.py` DI 수정 (§5)
- [ ] `docker compose up -d --build` 로 전체 기동
- [ ] `curl /health` → `"storage":"postgres"` 확인

---

## 1. DDL 스크립트 (`iot_init.sql`)

```sql
-- PostgreSQL 컨테이너 psql 에서 실행
CREATE TABLE IF NOT EXISTS iot_sensor_readings (
  id              VARCHAR(36) PRIMARY KEY,
  device_id       VARCHAR(64) NOT NULL,
  timestamp       TIMESTAMPTZ NOT NULL,
  soil_moisture   DOUBLE PRECISION NOT NULL,
  temperature     DOUBLE PRECISION NOT NULL,
  humidity        DOUBLE PRECISION NOT NULL,
  light_intensity INTEGER NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_iot_readings_device ON iot_sensor_readings(device_id);
CREATE INDEX IF NOT EXISTS ix_iot_readings_ts     ON iot_sensor_readings(timestamp DESC);

CREATE TABLE IF NOT EXISTS iot_irrigation_events (
  id             VARCHAR(36) PRIMARY KEY,
  triggered_at   TIMESTAMPTZ NOT NULL,
  reason         VARCHAR(255) NOT NULL DEFAULT '',
  valve_action   VARCHAR(10) NOT NULL,
  duration       INTEGER NOT NULL DEFAULT 0,
  auto_triggered BOOLEAN NOT NULL DEFAULT false,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_iot_irrigation_ts ON iot_irrigation_events(triggered_at DESC);

CREATE TABLE IF NOT EXISTS iot_sensor_alerts (
  id          VARCHAR(36) PRIMARY KEY,
  type        VARCHAR(32) NOT NULL,
  severity    VARCHAR(16) NOT NULL,
  message     VARCHAR(255) NOT NULL,
  timestamp   TIMESTAMPTZ NOT NULL,
  resolved    BOOLEAN NOT NULL DEFAULT false,
  resolved_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_iot_alerts_ts ON iot_sensor_alerts(timestamp DESC);
```

### 1.1 `iot_init.sql` 자동 적용 방식 (권장)

전용 컨테이너이므로 **psql 수동 실행 없이** Postgres 공식 이미지의 초기화 훅을 사용한다:

- `/docker-entrypoint-initdb.d/*.sql` 에 배치된 SQL 은 컨테이너 **최초 기동 시**(볼륨이 비어있을 때) 자동 실행된다.
- DB(`iotdb`) 자체도 `POSTGRES_DB` 환경변수로 자동 생성된다.
- 따라서 Relay 측 코드는 DDL 을 걱정할 필요 없이 그냥 연결만 하면 된다.

**파일 배치** (N100의 `iot_relay_server/` 디렉터리):

```
iot_relay_server/
├── docker-compose.yml
├── iot_init.sql          # ← 볼륨 마운트로 /docker-entrypoint-initdb.d/ 에 주입
├── .env
└── app/
    └── ...
```

**최초 기동 시퀀스**:

```
docker compose up -d
  ├─ iot-postgres 기동
  │    ├─ POSTGRES_DB=iotdb 로 DB 생성
  │    ├─ /docker-entrypoint-initdb.d/iot_init.sql 자동 실행 → 3 테이블 생성
  │    └─ healthcheck PASS
  └─ iot-relay 기동 (depends_on + service_healthy)
       └─ asyncpg Pool 연결 OK
```

### 1.2 수동 재적용이 필요한 경우

> 초기화 스크립트는 **볼륨이 비어있을 때만** 실행된다. 나중에 스키마를 변경하려면 수동 적용.

```bash
# N100 서버 콘솔에서
cd ~/iot_relay_server

# (A) 이미 떠 있는 iot-postgres 에 SQL 재적용
docker compose exec -T iot-postgres \
  psql -U iotuser -d iotdb < iot_init.sql
# IF NOT EXISTS 로 작성되어 있어 멱등 (여러 번 실행 OK)

# (B) 테이블 확인
docker compose exec iot-postgres psql -U iotuser -d iotdb -c "\dt iot_*"

# (C) 완전 리셋 (볼륨 삭제 후 재기동 → initdb 다시 실행)
docker compose down -v     # -v 가 핵심: 볼륨까지 삭제
docker compose up -d       # iot_init.sql 이 다시 자동 적용됨
```

### 1.3 검증

```bash
# 3 테이블 존재 확인
docker compose exec iot-postgres psql -U iotuser -d iotdb -c "\dt iot_*"

# 인덱스 확인
docker compose exec iot-postgres psql -U iotuser -d iotdb -c "\di ix_iot_*"

# 각 테이블 건수 (최초엔 모두 0)
docker compose exec iot-postgres psql -U iotuser -d iotdb -c \
  "SELECT 'readings' AS t, COUNT(*) FROM iot_sensor_readings
   UNION ALL SELECT 'events',   COUNT(*) FROM iot_irrigation_events
   UNION ALL SELECT 'alerts',   COUNT(*) FROM iot_sensor_alerts;"

# 헬스체크
docker compose exec iot-postgres pg_isready -U iotuser -d iotdb
```

### 1.4 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `iot_init.sql` 이 실행 안 됨 | 볼륨에 이미 데이터 존재 | `docker compose down -v` 후 재기동. 또는 §1.2 (A)로 수동 적용 |
| `FATAL: password authentication failed` | `.env` 의 `PG_PASSWORD` 가 볼륨 초기화 시점과 다름 | `down -v` 로 볼륨 리셋 후 재기동 (Postgres 는 첫 기동에만 env 반영) |
| iot-relay 가 `could not translate host name "iot-postgres"` | 동일 compose 네트워크에 없음 | 두 서비스 모두 `networks: [iot_net]` 에 속하는지 확인 |
| relay 기동이 postgres 보다 빨라 연결 실패 | depends_on 조건 부족 | `depends_on.iot-postgres.condition: service_healthy` + iot-postgres 에 `healthcheck` 정의 (아래 §6) |
| 한글 메시지 깨짐 | 로캘 미설정 | `POSTGRES_INITDB_ARGS=--encoding=UTF-8 --locale=C.UTF-8` 추가 |

---

## 2. `requirements.txt` 변경

```
fastapi==0.115.0
uvicorn==0.30.0
pydantic==2.9.0
pydantic-settings==2.5.0
asyncpg==0.30.0   # 추가
```

---

## 3. `app/store.py` 전체 교체

```python
"""IoT Relay PostgreSQL 저장소 (asyncpg 기반). FarmOS 로컬 BE 와 동일 스키마."""

import random
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import asyncpg

SOIL_MOISTURE_LOW = 55.0  # config 로 빼도 됨

_prev_soil_moisture: Optional[float] = None


def _estimate_soil_moisture(temperature: float, humidity: float, light_intensity: float) -> float:
    global _prev_soil_moisture
    base = 55.0
    humidity_effect = (humidity - 50) * 0.3
    temp_effect = (temperature - 20) * 0.4
    light_effect = (light_intensity / 100) * 2
    estimated = base + humidity_effect - temp_effect - light_effect + random.uniform(-2.0, 2.0)
    if _prev_soil_moisture is not None:
        estimated = _prev_soil_moisture * 0.7 + estimated * 0.3
    estimated = max(20.0, min(85.0, estimated))
    _prev_soil_moisture = estimated
    return round(estimated, 1)


def _reading_row(r: asyncpg.Record) -> dict:
    return {
        "device_id": r["device_id"],
        "timestamp": r["timestamp"].isoformat(),
        "soilMoisture": r["soil_moisture"],
        "temperature": r["temperature"],
        "humidity": r["humidity"],
        "lightIntensity": r["light_intensity"],
    }


def _alert_row(r: asyncpg.Record) -> dict:
    return {
        "id": r["id"],
        "type": r["type"],
        "severity": r["severity"],
        "message": r["message"],
        "timestamp": r["timestamp"].isoformat(),
        "resolved": r["resolved"],
    }


def _event_row(r: asyncpg.Record) -> dict:
    return {
        "id": r["id"],
        "triggeredAt": r["triggered_at"].isoformat(),
        "reason": r["reason"],
        "valveAction": r["valve_action"],
        "duration": r["duration"],
        "autoTriggered": r["auto_triggered"],
    }


async def add_reading(
    pool: asyncpg.Pool,
    device_id: str,
    sensors: dict,
    timestamp: datetime | None = None,
) -> list[dict]:
    ts = timestamp or datetime.now(timezone.utc)

    soil_moisture = sensors.get("soil_moisture")
    if soil_moisture is None:
        soil_moisture = _estimate_soil_moisture(
            temperature=sensors["temperature"],
            humidity=sensors["humidity"],
            light_intensity=sensors["light_intensity"],
        )

    new_alerts: list[dict] = []
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO iot_sensor_readings
                  (id, device_id, timestamp, soil_moisture, temperature, humidity, light_intensity)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                str(uuid4()), device_id, ts,
                soil_moisture, sensors["temperature"], sensors["humidity"], sensors["light_intensity"],
            )

            if soil_moisture < SOIL_MOISTURE_LOW:
                alert_id = str(uuid4())
                message = f"토양 습도가 {soil_moisture}%로 임계값 이하입니다"
                await conn.execute(
                    """
                    INSERT INTO iot_sensor_alerts (id, type, severity, message, timestamp)
                    VALUES ($1, 'moisture', '경고', $2, $3)
                    """,
                    alert_id, message, ts,
                )
                await conn.execute(
                    """
                    INSERT INTO iot_irrigation_events
                      (id, triggered_at, reason, valve_action, duration, auto_triggered)
                    VALUES ($1, $2, $3, '열림', 30, true)
                    """,
                    str(uuid4()), ts,
                    f"토양 습도 {soil_moisture}% — 임계값({SOIL_MOISTURE_LOW}%) 이하",
                )
                new_alerts.append({
                    "id": alert_id,
                    "type": "moisture",
                    "severity": "경고",
                    "message": message,
                    "timestamp": ts.isoformat(),
                    "resolved": False,
                })

            if sensors["humidity"] > 90:
                alert_id = str(uuid4())
                message = f"대기 습도 {sensors['humidity']}%. 병해 발생 위험 증가"
                await conn.execute(
                    """
                    INSERT INTO iot_sensor_alerts (id, type, severity, message, timestamp)
                    VALUES ($1, 'humidity', '주의', $2, $3)
                    """,
                    alert_id, message, ts,
                )
                new_alerts.append({
                    "id": alert_id,
                    "type": "humidity",
                    "severity": "주의",
                    "message": message,
                    "timestamp": ts.isoformat(),
                    "resolved": False,
                })

    return new_alerts


async def get_latest(pool: asyncpg.Pool) -> dict | None:
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT * FROM iot_sensor_readings ORDER BY timestamp DESC LIMIT 1"
        )
    return _reading_row(r) if r else None


async def get_history(pool: asyncpg.Pool, limit: int = 300) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM iot_sensor_readings ORDER BY timestamp DESC LIMIT $1",
            limit,
        )
    items = [_reading_row(r) for r in rows]
    items.reverse()
    return items


async def get_alerts(pool: asyncpg.Pool, resolved: bool | None = None) -> list[dict]:
    async with pool.acquire() as conn:
        if resolved is None:
            rows = await conn.fetch(
                "SELECT * FROM iot_sensor_alerts ORDER BY timestamp DESC"
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM iot_sensor_alerts WHERE resolved = $1 ORDER BY timestamp DESC",
                resolved,
            )
    return [_alert_row(r) for r in rows]


async def resolve_alert(pool: asyncpg.Pool, alert_id: str) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE iot_sensor_alerts SET resolved = true, resolved_at = now() WHERE id = $1",
            alert_id,
        )
    # asyncpg 는 "UPDATE <n>" 문자열을 반환
    return result.endswith(" 1") or result.endswith(" 1\n")


async def get_irrigation_events(pool: asyncpg.Pool) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM iot_irrigation_events ORDER BY triggered_at DESC"
        )
    return [_event_row(r) for r in rows]


async def add_irrigation_event(pool: asyncpg.Pool, valve_action: str, reason: str) -> dict:
    event_id = str(uuid4())
    now = datetime.now(timezone.utc)
    duration = 30 if valve_action == "열림" else 0
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            """
            INSERT INTO iot_irrigation_events
              (id, triggered_at, reason, valve_action, duration, auto_triggered)
            VALUES ($1, $2, $3, $4, $5, false)
            RETURNING *
            """,
            event_id, now, reason or "수동 제어", valve_action, duration,
        )
    return _event_row(r)


async def get_counts(pool: asyncpg.Pool) -> dict:
    async with pool.acquire() as conn:
        readings = await conn.fetchval("SELECT COUNT(*) FROM iot_sensor_readings")
        events = await conn.fetchval("SELECT COUNT(*) FROM iot_irrigation_events")
        alerts = await conn.fetchval("SELECT COUNT(*) FROM iot_sensor_alerts")
    return {
        "readings_count": int(readings or 0),
        "irrigation_events_count": int(events or 0),
        "alerts_count": int(alerts or 0),
    }
```

---

## 4. `app/main.py` lifespan 패치

```python
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import sensors, irrigation, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    dsn = os.environ["DATABASE_URL"]
    # asyncpg 전용 DSN (postgresql+asyncpg:// 접두사 제거)
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    app.state.db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    try:
        yield
    finally:
        await app.state.db_pool.close()


app = FastAPI(title="IoT Relay Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sensors.router, prefix="/api/v1")
app.include_router(irrigation.router, prefix="/api/v1")
app.include_router(health.router)
```

---

## 5. 라우터 DI (`app/api/sensors.py` 예시)

```python
from fastapi import APIRouter, Depends, Query, Request
from app import store

router = APIRouter(prefix="/sensors", tags=["sensors"])


def get_pool(request: Request):
    return request.app.state.db_pool


@router.post("", status_code=201)
async def receive_sensor_data(data: SensorDataIn, pool=Depends(get_pool)):
    new_alerts = await store.add_reading(
        pool,
        device_id=data.device_id,
        sensors=data.sensors.model_dump(),
        timestamp=data.timestamp,
    )
    return {"status": "ok", "alerts_generated": len(new_alerts)}


@router.get("/latest")
async def get_latest_reading(pool=Depends(get_pool)):
    reading = await store.get_latest(pool)
    if reading is None:
        return {"timestamp": None, "soilMoisture": 0, "temperature": 0, "humidity": 0, "lightIntensity": 0}
    return reading


@router.get("/history")
async def get_sensor_history(limit: int = Query(300, ge=1, le=2000), pool=Depends(get_pool)):
    return await store.get_history(pool, limit)


@router.get("/alerts")
async def get_sensor_alerts(resolved: bool | None = None, pool=Depends(get_pool)):
    return await store.get_alerts(pool, resolved)


@router.patch("/alerts/{alert_id}/resolve")
async def resolve_sensor_alert(alert_id: str, pool=Depends(get_pool)):
    ok = await store.resolve_alert(pool, alert_id)
    return {"status": "resolved"} if ok else {"error": "alert not found"}
```

`irrigation.py` / `health.py` 도 동일 패턴으로 `pool=Depends(get_pool)` 주입 후 `await store.*` 호출.

---

## 6. `docker-compose.yml` 전체 (전용 컨테이너)

`iot_relay_server/docker-compose.yml`:

```yaml
services:
  iot-postgres:
    image: postgres:16-alpine
    container_name: iot-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${PG_USER}
      POSTGRES_PASSWORD: ${PG_PASSWORD}
      POSTGRES_DB: ${PG_DB}
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --locale=C.UTF-8"
      TZ: Asia/Seoul
    volumes:
      - iot_pgdata:/var/lib/postgresql/data
      - ./iot_init.sql:/docker-entrypoint-initdb.d/01-iot_init.sql:ro
    networks:
      - iot_net
    # 기본은 외부 포트 미노출. 디버깅 필요 시 아래 주석 해제 (호스트 5433 → 컨테이너 5432)
    # ports:
    #   - "127.0.0.1:5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_USER} -d ${PG_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10

  iot-relay:
    build: .
    container_name: iot-relay
    restart: unless-stopped
    depends_on:
      iot-postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${PG_USER}:${PG_PASSWORD}@iot-postgres:5432/${PG_DB}
      IOT_API_KEY: ${IOT_API_KEY}
      TZ: Asia/Seoul
    ports:
      - "9000:9000"
    networks:
      - iot_net

volumes:
  iot_pgdata:
    name: iot_pgdata

networks:
  iot_net:
    name: iot_net
    driver: bridge
```

**`.env` 예시** (`iot_relay_server/.env`, 리포지토리 커밋 금지):

```
PG_USER=iotuser
PG_PASSWORD=change_me_strong_password
PG_DB=iotdb
IOT_API_KEY=farmos-iot-default-key
```

**주요 설계 포인트**:

- 별도 `iot_net` 네트워크 — 기존 다른 Postgres 와 **완전 분리**
- `iot_pgdata` 이름 있는 볼륨 — 컨테이너 삭제해도 데이터 유지
- `depends_on.condition: service_healthy` — Postgres 준비 전에 Relay 가 뜨는 레이스 방지
- 포트 미노출 — ESP8266 은 Relay API(9000) 만 접근, DB 직접 노출 없음
- 한글 로캘 설정으로 알림 메시지 깨짐 방지

---

## 7. 기동 & 검증

```bash
# N100 서버에서
cd ~/iot_relay_server

# 최초 기동 (initdb 가 iot_init.sql 자동 적용)
docker compose up -d --build

# 로그로 초기화 확인
docker compose logs iot-postgres | grep -i "iot_init\|database system is ready"
# 기대: "running /docker-entrypoint-initdb.d/01-iot_init.sql" 라인이 보여야 함

# 테이블 확인
docker compose exec iot-postgres psql -U iotuser -d iotdb -c "\dt iot_*"

# Relay 헬스체크
curl -s http://localhost:9000/health | jq
# 기대: {"status":"ok","storage":"postgres","readings_count":0,...}

# ESP8266 POST 시뮬레이션
curl -XPOST http://localhost:9000/api/v1/sensors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: farmos-iot-default-key" \
  -d '{"device_id":"esp8266-test","sensors":{"temperature":25,"humidity":60,"light_intensity":30000}}'

# DB 직접 확인
docker compose exec iot-postgres psql -U iotuser -d iotdb \
  -c "SELECT COUNT(*) FROM iot_sensor_readings;"

# 영속성 검증: Relay 만 재기동해도 데이터 유지
docker compose restart iot-relay
curl -s "http://localhost:9000/api/v1/sensors/history?limit=5" | jq 'length'
# 기대: 1 이상

# 완전 재기동(볼륨 유지)도 데이터 유지
docker compose down
docker compose up -d
curl -s "http://localhost:9000/api/v1/sensors/history?limit=5" | jq 'length'
# 기대: 1 이상
```

---

## 8. 운영 팁

### 8.1 백업 (전용 컨테이너이므로 독립 스크립트)

```bash
# 일일 덤프 예시 (cron 등에 등록)
docker compose exec -T iot-postgres \
  pg_dump -U iotuser -d iotdb --clean --if-exists \
  | gzip > /backup/iot_$(date +%Y%m%d).sql.gz

# 복구
gunzip -c /backup/iot_20260420.sql.gz | \
  docker compose exec -T iot-postgres psql -U iotuser -d iotdb
```

### 8.2 오래된 데이터 정리 (선택)

30초 주기 INSERT 가 수개월 누적되면 수백만 행이 된다. 필요 시 TTL 삭제:

```sql
-- 90일 이전 센서 데이터 삭제 (예시)
DELETE FROM iot_sensor_readings WHERE timestamp < now() - INTERVAL '90 days';
VACUUM iot_sensor_readings;
```

### 8.3 리소스 제한 (N100 저사양 고려 시)

`docker-compose.yml` 의 각 서비스에 추가:

```yaml
    deploy:
      resources:
        limits:
          memory: 256M
```

## 9. 롤백 절차

전환에 문제가 발생하면:

1. `git checkout <이전-store.py-커밋>` 으로 Relay 코드 복구
2. `docker compose up -d --build` (iot-relay 만 재빌드)
3. Relay 가 기존 인메모리 버전으로 돌아가면 `iot-postgres` 컨테이너는 그대로 두어도 무관
4. 완전 제거를 원하면: `docker compose down -v` + `docker volume rm iot_pgdata`

---

## 10. AI Agent Decision 영속화 (agent-action-history, 2026-04-20)

> **배경**: FarmOS 의 `agent-action-history` feature 가 Relay decisions 를 FarmOS Postgres 로 SSE Bridge 하려면,
> Relay 도 decisions 를 DB 에 영속 저장해야 한다 (현재는 `List[AIDecision]` 인메모리 20 건 보유).
>
> **원칙**: Relay 는 **원본 master** 역할. FarmOS 는 최근 30 일 mirror + 집계.
>
> **관련 문서**: `docs/01-plan/features/agent-action-history.plan.md`, `docs/02-design/features/agent-action-history.design.md` §2.3 / §4

### 10.1 DDL 추가 (`iot_init.sql` 말미에 append)

```sql
-- AI Agent 판단 이력 (agent-action-history)
CREATE TABLE IF NOT EXISTS iot_agent_decisions (
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
CREATE INDEX IF NOT EXISTS ix_iot_agent_decisions_timestamp_desc
  ON iot_agent_decisions (timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_iot_agent_decisions_created_desc
  ON iot_agent_decisions (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_iot_agent_decisions_ctype
  ON iot_agent_decisions (control_type);
CREATE INDEX IF NOT EXISTS ix_iot_agent_decisions_source
  ON iot_agent_decisions (source);
```

> 이미 운영 중 컨테이너에 적용하려면 §1.2 (A) 수동 재적용 방식 사용:
> `docker compose exec -T iot-postgres psql -U iotuser -d iotdb < iot_init.sql`

### 10.2 Relay `app/store.py` 에 함수 추가

```python
from typing import Optional

async def add_agent_decision(pool: asyncpg.Pool, decision: dict) -> dict:
    """AI Agent 판단 1건을 INSERT. id 는 호출자가 UUID 생성."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO iot_agent_decisions
              (id, timestamp, control_type, priority, source, reason,
               action, tool_calls, sensor_snapshot, duration_ms)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9::jsonb, $10)
            ON CONFLICT (id) DO NOTHING
            """,
            decision["id"], decision["timestamp"],
            decision["control_type"], decision["priority"], decision["source"],
            decision.get("reason", ""),
            json.dumps(decision.get("action") or {}),
            json.dumps(decision.get("tool_calls") or []),
            json.dumps(decision.get("sensor_snapshot")) if decision.get("sensor_snapshot") else None,
            decision.get("duration_ms"),
        )
    return decision


async def list_agent_decisions(
    pool: asyncpg.Pool,
    limit: int = 20,
    cursor: Optional[datetime] = None,
    since: Optional[datetime] = None,
    control_type: Optional[str] = None,
    source: Optional[str] = None,
    priority: Optional[str] = None,
) -> dict:
    """cursor(created_at < :cursor) 기반 pagination. 구 API 호환: since 만 주면 timestamp >= since."""
    conds = ["1=1"]
    params: list = []
    if cursor is not None:
        params.append(cursor); conds.append(f"created_at < ${len(params)}")
    if since is not None:
        params.append(since); conds.append(f"timestamp >= ${len(params)}")
    if control_type:
        params.append(control_type); conds.append(f"control_type = ${len(params)}")
    if source:
        params.append(source); conds.append(f"source = ${len(params)}")
    if priority:
        params.append(priority); conds.append(f"priority = ${len(params)}")
    params.append(limit + 1)
    query = f"""
        SELECT * FROM iot_agent_decisions
        WHERE {' AND '.join(conds)}
        ORDER BY created_at DESC
        LIMIT ${len(params)}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    items = [_decision_row(r) for r in rows[:limit]]
    has_more = len(rows) > limit
    next_cursor = items[-1]["created_at"] if has_more and items else None
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_agent_decision(pool: asyncpg.Pool, decision_id: str) -> Optional[dict]:
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT * FROM iot_agent_decisions WHERE id = $1", decision_id
        )
    return _decision_row(r) if r else None


def _decision_row(r: asyncpg.Record) -> dict:
    return {
        "id": r["id"],
        "timestamp": r["timestamp"].isoformat(),
        "control_type": r["control_type"],
        "priority": r["priority"],
        "source": r["source"],
        "reason": r["reason"],
        "action": r["action"],                # asyncpg 는 JSONB 를 dict 로 자동 변환
        "tool_calls": r["tool_calls"],
        "sensor_snapshot": r["sensor_snapshot"],
        "duration_ms": r["duration_ms"],
        "created_at": r["created_at"].isoformat(),
    }
```

### 10.3 Relay `app/api/ai_agent.py` — 신규 엔드포인트

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from datetime import datetime
from app import store

router = APIRouter(prefix="/ai-agent", tags=["ai-agent"])


def get_pool(request: Request):
    return request.app.state.db_pool


@router.get("/decisions")
async def list_decisions(
    limit: int = Query(20, ge=1, le=200),
    cursor: datetime | None = None,
    since: datetime | None = None,
    control_type: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    pool=Depends(get_pool),
):
    """
    cursor(created_at DESC) 기반 pagination.
    구버전 호환: cursor/필터 없이 limit 만 주면 최신 N 건 리스트 반환.
    """
    result = await store.list_agent_decisions(
        pool, limit=limit, cursor=cursor, since=since,
        control_type=control_type, source=source, priority=priority,
    )
    return result  # {items, next_cursor, has_more}


@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str, pool=Depends(get_pool)):
    row = await store.get_agent_decision(pool, decision_id)
    if row is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return row
```

### 10.4 AI Engine 판단 생성 시점 Hook

기존 AI 판단 로직이 `AIDecision` 을 만들고 SSE 로 브로드캐스트하는 지점에, DB insert 를 **먼저** 추가한다:

```python
# AI Engine 판단 완료 직후 (SSE broadcast 이전)
decision_dict = {
    "id": str(uuid4()),
    "timestamp": datetime.now(timezone.utc),
    "control_type": decision.control_type,
    "priority": decision.priority,
    "source": decision.source,
    "reason": decision.reason,
    "action": decision.action,
    "tool_calls": [tc.model_dump() for tc in decision.tool_calls],
    "sensor_snapshot": {
        "temperature": latest_sensor.temperature,
        "humidity": latest_sensor.humidity,
        "light_intensity": latest_sensor.light_intensity,
        "soil_moisture": latest_sensor.soil_moisture,
        "timestamp": latest_sensor.timestamp.isoformat(),
    },
    "duration_ms": int((time.monotonic() - start) * 1000),
}
await store.add_agent_decision(pool, decision_dict)

# 그 다음 SSE 브로드캐스트 (payload 에 id / sensor_snapshot / duration_ms 포함)
await sse_broadcast("ai_decision", decision_dict)
```

### 10.5 SSE 이벤트 payload shape (기존 → 신규)

Relay `/api/v1/ai-agent/stream` 의 `ai_decision` 이벤트 data 에 **optional 필드 추가** (기존 소비자 호환 유지):

```json
// 기존 (유지)
{
  "id": "uuid...",
  "timestamp": "2026-04-20T08:41:13+09:00",
  "control_type": "ventilation",
  "priority": "high",
  "source": "llm",
  "reason": "CO2 상승",
  "action": {"window_open_pct": 60},
  "tool_calls": [...]
}
// 신규 추가 필드 (선택, 있으면 FarmOS Bridge 가 그대로 저장)
{
  "...": "...",
  "sensor_snapshot": {"temperature": 29.3, "humidity": 62.1, "light_intensity": 18400},
  "duration_ms": 388
}
```

### 10.6 체크리스트

- [ ] `iot_init.sql` 말미에 §10.1 DDL append
- [ ] `app/store.py` 에 §10.2 3 함수 추가 (import: `json`, `from typing import Optional`)
- [ ] `app/api/ai_agent.py` (신규 또는 기존 파일에 라우터 추가)
- [ ] `app/main.py` 에 `app.include_router(ai_agent.router, prefix="/api/v1")`
- [ ] AI Engine 판단 지점에 §10.4 hook 추가
- [ ] SSE 브로드캐스트 payload 에 sensor_snapshot/duration_ms 포함
- [ ] `docker compose up -d --build` 후 `curl http://localhost:9000/api/v1/ai-agent/decisions?limit=1` 로 검증
- [ ] FarmOS BE `.env` 에서 `AI_AGENT_BRIDGE_ENABLED=true` 로 전환 → 로그 `ai_agent_bridge.started` / `backfill_done` 확인

### 10.8 ⚠️ asyncpg parameter type 주의사항 (2026-04-20 추가)

FarmOS Bridge 의 요약 UPSERT SQL (`backend/app/services/ai_agent_bridge.py` `_bump_daily` / `_bump_hourly`) 에서
다음 패턴은 **asyncpg prepared statement 가 parameter 타입을 추론하지 못해 `AmbiguousParameterError` 발생**:

```sql
-- ❌ 실패 — $3 type unknown
jsonb_build_object(:src, 1)
ARRAY[:src]

-- ✅ 수정 — CAST 로 text 명시
jsonb_build_object(CAST(:src AS text), 1)
ARRAY[CAST(:src AS text)]
```

**원인**: `jsonb_build_object` 의 첫 인자는 text, `ARRAY[...]` 는 element 타입 추론 필요. asyncpg 가 같은 parameter 를 여러 위치에서 쓰는 prepared statement 를 만들 때 타입 일관성을 보장하지 못함.

**영향 범위**: FarmOS Bridge 코드만 (Relay `app/store.py` 는 asyncpg 의 `$N` positional 파라미터를 직접 사용하므로 이 문제 무관). Relay 측 patch 에는 영향 없음.

> 위 수정은 FarmOS 리포(`ai_agent_bridge.py` + `seed_ai_agent.py`) 에 이미 반영됨. Relay 측 `app/store.py` 의 `add_agent_decision` / `list_agent_decisions` 은 asyncpg native 파라미터를 쓰므로 그대로 §10.2 스펙대로 구현하면 됨.

### 10.7 FarmOS 측 검증 (적용 후)

```bash
# FarmOS BE 재시작 (AI_AGENT_BRIDGE_ENABLED=true)
curl -s http://localhost:8000/api/v1/ai-agent/bridge/status
# 기대: {"enabled":true,"healthy":true,"last_event_at":"...","total_processed":N,...}

# 미러 건수 확인
psql -d farmos -c "SELECT COUNT(*) FROM ai_agent_decisions;"
# Relay 건수와 ±1 이내여야 함

# 요약 API
curl -s "http://localhost:8000/api/v1/ai-agent/activity/summary?range=today"
```
