-- FarmOS 로컬 DB의 레거시 IoT 테이블 제거 (2026-04-21)
--
-- 배경:
--   IoT 센서/알림/관수 데이터의 단일 원천(SSoT)은 iot_relay_server 의 `iotdb` 로 확정되었다.
--   FarmOS 백엔드의 `iot_*` 3개 테이블은 Relay 도입 이전의 레거시이며, 현재 아키텍처에서
--   프런트·백엔드 어느 쪽도 insert/select 하지 않는다. Bridge 미러링 대상도 아니다.
--
-- 적용 방법 (최초 1회만, 수동 실행):
--   psql "postgresql://postgres:postgres@localhost:5432/farmos" -f drop_iot_legacy_tables.sql
--
-- 멱등: IF EXISTS 사용 — 재실행 안전.
-- 되돌리기: 필요 시 git log 에서 본 커밋을 revert 하면 SQLAlchemy Base.metadata.create_all 이
--           다음 기동 시 테이블을 재생성한다 (데이터는 복원되지 않음).

BEGIN;

DROP TABLE IF EXISTS iot_sensor_readings;
DROP TABLE IF EXISTS iot_sensor_alerts;
DROP TABLE IF EXISTS iot_irrigation_events;

COMMIT;
