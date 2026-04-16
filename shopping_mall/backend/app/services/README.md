# app/services/

비즈니스 로직 레이어. 라우터에서 직접 DB를 다루지 않고 서비스를 통해 처리합니다.

## 파일

| 파일 | 역할 |
|------|------|
| `agent_chatbot.py` | 챗봇 메인 서비스 — `AgentExecutor`를 래핑해 라우터 인터페이스(`answer()`) 제공. ChatLog/ChatSession 저장 포함 |
| `ai_classifier.py` | 비용 항목 자동 분류 — Ollama LLM 또는 키워드 룰 폴백으로 `ExpenseEntry.category` 채움 |
| `ai_report.py` | 주간 리포트 생성 — 매출/비용/인기상품 집계 후 Ollama LLM으로 인사이트 텍스트 생성 |
| `demand_forecaster.py` | 수요 예측 |
| `revenue_sync.py` | 주문 데이터 → `RevenueEntry` 동기화 |
| `rfm_analyzer.py` | RFM(Recency·Frequency·Monetary) 기반 고객 세그먼트 분석 |
| `shipping_tracker.py` | 배송 상태 추적 및 갱신 |

## 챗봇 흐름

```text
POST /api/chatbot/ask
  → app/routers/chatbot.py
  → AgentChatbotService.answer()
  → AgentExecutor.run()          # ai/agent/executor.py
  → LLM tool_use 루프
  → ChatLog 저장
```
