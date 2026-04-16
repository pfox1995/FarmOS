# jobs/

APScheduler 기반 정기 작업. `app/main.py` lifespan에서 스케줄러가 시작됩니다.

## 파일

| 파일 | 역할 |
|------|------|
| `scheduler.py` | 스케줄러 설정 — 각 job을 cron 표현식으로 등록 |
| `generate_report.py` | 매주 월요일 전주 매출 리포트 자동 생성 (`ReportService` 호출) |
| `check_shipments.py` | 주기적으로 배송 상태 확인 및 갱신 |
| `update_segments.py` | RFM 분석으로 고객 세그먼트 갱신 |
