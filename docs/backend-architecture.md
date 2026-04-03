# FarmOS Backend Architecture

## 기술 스택

| 항목 | 기술 | 버전 |
|------|------|------|
| 언어 | Python | 3.12 |
| 패키지 관리 | uv | 0.11.2 |
| 웹 프레임워크 | FastAPI | 0.135.2 |
| 설정 관리 | pydantic-settings | 2.13.1 |
| ASGI 서버 | uvicorn | 0.42.0 |
| 데이터 저장 (인증) | PostgreSQL 18 | asyncpg |
| 데이터 저장 (IoT) | **인메모리** (시연용) | - |

> IoT 센서 데이터는 시연 목적의 인메모리 저장소를 사용한다. 서버 재시작 시 센서 데이터는 초기화된다.
> 사용자 인증 데이터는 PostgreSQL `farmos` DB에 영속 저장된다.

---

## 프로젝트 구조

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI 앱 (CORS, 라우터 등록)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # pydantic-settings 환경 설정
│   │   └── store.py           # 인메모리 저장소 (deque + list)
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── sensor.py          # Pydantic 입력 스키마
│   └── api/
│       ├── __init__.py
│       ├── health.py          # GET /health
│       ├── sensors.py         # POST/GET 센서 데이터 + 알림
│       └── irrigation.py      # POST/GET 관개 제어
├── main.py                    # uvicorn 진입점
├── .env                       # 환경 변수
├── .env.example
├── .gitignore
├── pyproject.toml
└── uv.lock
```

---

## 인메모리 저장소 (`app/core/store.py`)

| 저장소 | 자료구조 | 최대 크기 | 설명 |
|--------|---------|----------|------|
| `sensor_readings` | `deque` | 2,000건 | 센서 데이터 (FIFO, 약 16시간분) |
| `irrigation_events` | `list` | 무제한 | 관개 이벤트 |
| `sensor_alerts` | `list` | 무제한 | 센서 알림 |

서버 재시작 시 모든 데이터가 초기화된다. 시연 중에는 ESP8266이 주기적으로 POST하므로 데이터가 자동 축적된다.

---

## API 엔드포인트

Base URL: `/api/v1`

### Health

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/health` | 서버 상태 + 인메모리 데이터 건수 |

응답 예시:
```json
{
  "status": "ok",
  "storage": "in-memory",
  "readings_count": 150,
  "irrigation_events_count": 2,
  "alerts_count": 3
}
```

### Sensors

| 메서드 | 경로 | 설명 | 파라미터 |
|--------|------|------|----------|
| `POST` | `/sensors` | ESP8266 센서 데이터 수신 | body: `SensorDataIn` |
| `GET` | `/sensors/latest` | 최신 센서 값 1건 | - |
| `GET` | `/sensors/history` | 센서 데이터 목록 (시간순) | `limit` (1~2000, 기본 300) |
| `GET` | `/sensors/alerts` | 알림 목록 | `resolved` (optional) |
| `PATCH` | `/sensors/alerts/{alert_id}/resolve` | 알림 해결 처리 | - |

### Irrigation

| 메서드 | 경로 | 설명 | 파라미터 |
|--------|------|------|----------|
| `POST` | `/irrigation/trigger` | 수동 관개 밸브 제어 | body: `IrrigationTriggerIn` |
| `GET` | `/irrigation/events` | 관개 이력 (최신순) | - |

---

## 데이터 흐름

```
┌─────────────────┐     HTTP POST       ┌──────────────────┐     GET        ┌──────────────┐
│   ESP8266        │ ──────────────────→ │  FastAPI          │ ────────────→ │  React 프론트  │
│   DHT11 (온습도)  │  /api/v1/sensors   │  인메모리 저장소    │  /latest     │  IoTDashboard │
│   포토레지스터    │  (snake_case)       │  (deque + list)   │  /history    │  Page.tsx     │
│   토양습도센서    │                     │                   │  (camelCase) │              │
└─────────────────┘                     └──────────────────┘              └──────────────┘
```

---

## ESP8266 POST 페이로드 (snake_case)

```json
{
  "device_id": "farmos-esp-001",
  "timestamp": "2026-03-15T14:30:00Z",
  "sensors": {
    "temperature": 22.5,
    "humidity": 65.3,
    "soil_moisture": 58.2,
    "light_intensity": 340
  }
}
```

## 프론트엔드 응답 (camelCase)

```json
{
  "timestamp": "2026-03-15T14:30:00Z",
  "soilMoisture": 58.2,
  "temperature": 22.5,
  "humidity": 65.3,
  "lightIntensity": 340
}
```

snake→camelCase 변환은 `store.py`의 `add_reading()`에서 저장 시점에 처리한다.

---

## 자동 관개 트리거 로직

`POST /api/v1/sensors` 수신 시 자동 실행:

| 조건 | 동작 |
|------|------|
| `soil_moisture < 55%` | `IrrigationEvent(열림)` + `SensorAlert(경고)` 자동 생성 |
| `humidity > 90%` | `SensorAlert(주의, "병해 발생 위험")` 자동 생성 |

임계값은 `.env`의 `SOIL_MOISTURE_LOW`, `SOIL_MOISTURE_HIGH`로 조정.

---

## 환경 변수 (.env)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `CORS_ORIGINS` | `["http://localhost:5173"]` | 허용 CORS 도메인 |
| `SOIL_MOISTURE_LOW` | `55.0` | 관개 트리거 하한 (%) |
| `SOIL_MOISTURE_HIGH` | `70.0` | 관개 중단 상한 (%) |

---

## 실행 방법

```bash
cd backend

# 서버 실행 (hot reload)
uv run python main.py

# Swagger 문서
# http://localhost:8000/docs
```

PostgreSQL `farmos` DB가 필요하다. 테이블은 서버 시작 시 자동 생성된다.

---

## 프론트엔드 연동 가이드

현재 프론트엔드(`IoTDashboardPage.tsx`)는 Mock 데이터를 사용 중. 실제 API로 전환하려면:

1. `src/hooks/useSensorData.ts` 커스텀 훅 생성 (fetch polling)
2. `IoTDashboardPage.tsx`에서 Mock import를 훅으로 교체
3. `.env`에 `VITE_API_URL=http://localhost:8000/api/v1` 추가
4. `VITE_USE_MOCK_SENSORS=true/false`로 Mock/실제 모드 전환
