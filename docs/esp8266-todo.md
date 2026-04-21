# ESP8266 IoT 연동 작업 목록 (2026-04-02)

> ⚠️ **DEPRECATED (2026-04-21)** — 이 문서의 `localhost:8000/api/v1/sensors*` curl 예시는 **현재 아키텍처에서 유효하지 않습니다.**
> ESP8266은 N100 서버의 IoT Relay(`http://iot.lilpa.moe/api/v1/sensors`)로 직접 POST하며, FarmOS 백엔드의 `iot_*` 레거시 테이블/엔드포인트는 제거되었습니다.
> 현 구조는 `docs/iot-relay-server-plan.md` 참조. 아래 내용은 Relay 도입 이전의 이력으로만 남겨둡니다.

## 현재 상태 (legacy)

- 백엔드 API 준비 완료 (`POST /api/v1/sensors`)
- 프론트엔드 3초 폴링 연동 완료 (`useSensorData` 훅)
- 토양 습도: 센서 미보유 → 서버에서 20.0~90.0% 랜덤 생성
- 온도, 대기 습도, 조도: ESP8266 실측값 수신 대기 중

---

## 작업 1: ESP8266 펌웨어 작성

### 센서 구성

| 센서 | 측정 항목 | 연결 핀 |
|------|----------|---------|
| DHT11 | 온도(°C), 대기 습도(%) | D4 (GPIO2) |
| 포토레지스터 (CdS) | 조도 (lux) | A0 (ADC) |

### 필요 라이브러리

- `ESP8266WiFi.h` — WiFi 연결
- `ESP8266HTTPClient.h` — HTTP POST 전송
- `DHT.h` — DHT11 센서 읽기
- `ArduinoJson.h` — JSON 직렬화

### 펌웨어 흐름

```
1. WiFi 연결 (SSID, PASSWORD 설정)
2. 루프 (30초 간격):
   a. DHT11에서 온도/습도 읽기
   b. A0에서 조도 읽기
   c. JSON 페이로드 구성
   d. HTTP POST → http://{서버IP}:8000/api/v1/sensors
   e. 응답 확인
```

### POST 페이로드 형식

```json
{
  "device_id": "farmos-esp-001",
  "sensors": {
    "temperature": 22.5,
    "humidity": 65.3,
    "light_intensity": 340
  }
}
```

> `soil_moisture` 생략 시 서버가 20.0~90.0% 난수 자동 생성

---

## 작업 2: WiFi 설정

ESP8266과 백엔드 서버가 **같은 네트워크**에 있어야 함

```cpp
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* serverUrl = "http://서버IP:8000/api/v1/sensors";
```

서버 IP 확인: `ipconfig` (Windows) → IPv4 주소 사용

---

## 작업 3: 테스트 순서

1. **서버 기동**: `cd backend && uv run python main.py`
2. **프론트엔드 기동**: `cd frontend && npm run dev`
3. **ESP8266 업로드**: Arduino IDE에서 스케치 업로드
4. **확인 사항**:
   - 백엔드 콘솔에 POST 수신 로그
   - `http://localhost:8000/api/v1/sensors/latest`에서 실측값 확인
   - 프론트엔드 IoT 대시보드에서 3초마다 값 갱신 확인
   - 토양 습도가 55% 이하일 때 알림/관수 자동 생성 확인

---

## 작업 4: curl로 사전 테스트 (ESP8266 없이)

ESP8266 연결 전에 API가 정상 동작하는지 확인:

```bash
curl -X POST http://localhost:8000/api/v1/sensors \
  -H "Content-Type: application/json" \
  -d '{"device_id":"test-001","sensors":{"temperature":23.1,"humidity":58.0,"light_intensity":420}}'
```

응답: `{"status":"ok","alerts_generated":0}`

최신값 확인:
```bash
curl http://localhost:8000/api/v1/sensors/latest
```

---

## 참고: 백엔드 API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/v1/sensors` | 센서 데이터 수신 |
| `GET` | `/api/v1/sensors/latest` | 최신 센서 값 1건 |
| `GET` | `/api/v1/sensors/history?limit=100` | 시계열 데이터 |
| `GET` | `/api/v1/sensors/alerts` | 알림 목록 |
| `POST` | `/api/v1/irrigation/trigger` | 수동 관개 제어 |
| `GET` | `/api/v1/irrigation/events` | 관개 이력 |

---

## 주의 사항

- ESP8266의 ADC(A0)는 0~1V 입력 → 포토레지스터 분압 회로 필요
- DHT11은 읽기 간격 최소 2초 → 전송 주기 30초면 충분
- WiFi 끊김 대비 재연결 로직 포함할 것
- 서버 CORS 설정 완료 (`localhost:5173`, `localhost:3000` 허용)
