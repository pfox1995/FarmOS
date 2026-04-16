# ai/agent/

tool_use 기반 챗봇 에이전트 서브패키지.

## 파일

| 파일 | 역할 |
|------|------|
| `executor.py` | 에이전트 루프 — LLM 호출 → 도구 실행 → 반복. `AgentExecutor`, `AgentResult`, `RequestContext` 정의 |
| `tools.py` | 12개 도구의 JSON Schema 정의 (`TOOL_DEFINITIONS`, `TOOL_TO_INTENT`) |
| `holiday.py` | 한국천문연구원 공휴일 API 클라이언트 + 월별 메모리 캐시. 배송 예정일 보정에 사용 |
| `prompts.py` | 에이전트 시스템 프롬프트 (`AGENT_SYSTEM_PROMPT`) — 페르소나, 도구 사용 원칙, 답변 스타일 |

## 서브패키지

| 디렉터리 | 역할 |
|----------|------|
| `clients/` | LLM 클라이언트 구현체 (OpenAI 호환, Claude) |

## 12개 도구 요약

| 도구 | 유형 | 설명 |
|------|------|------|
| `search_faq` | RAG | 일반 운영 FAQ |
| `search_storage_guide` | RAG | 농산물 보관 방법 |
| `search_season_info` | RAG | 제철 농산물 정보 |
| `search_policy` | RAG | 6개 정책 문서 (return/payment/delivery/quality/service/membership) |
| `get_order_status` | DB | 주문·배송 현황 + 공휴일 기반 도착일 보정 |
| `search_products` | DB | 상품 검색·재고 확인 |
| `get_product_detail` | DB | 상품 상세 정보 |
| `search_farm_info` | RAG | 농장·플랫폼 소개 |
| `escalate_to_agent` | Action | 상담원 에스컬레이션 |
| `create_exchange_request` | Write | 교환 신청 접수 (PENDING 상태로 저장 후 사용자 확인 요청) |
| `confirm_pending_action` | Write | 대기 중인 액션 최종 실행 (사용자가 동의했을 때) |
| `cancel_pending_action` | Write | 대기 중인 액션 취소 (사용자가 거부했을 때) |

## RequestContext

`AgentExecutor.run()` 호출 시 시스템 프롬프트 뒤에 자동으로 현재 시각과 로그인 상태가 주입됩니다.

```text
[현재 시각] 2026-04-14 (월) 14:32
[로그인 상태] 로그인 (user_id=5)
```

## Human-in-the-Loop (교환 신청 확인 플로우)

쓰기 작업(교환 신청 등)은 즉시 실행하지 않고 사용자 확인 후 처리합니다.

```text
사용자: "주문 123번 교환 신청해줘"
  → LLM: create_exchange_request(order_id=123, reason="...")
     └─ DB: ExchangeRequest(status="pending_confirm") 생성
     └─ ChatSession.pending_action = {"type": "exchange_request", "exchange_request_id": 42, "summary": "..."}
     └─ 챗봇: "교환 신청 내용을 확인해드릴게요. [내용] 신청하시겠어요?"

사용자: "네, 신청해줘"
  → LLM: confirm_pending_action()
     └─ pending_action에서 exchange_request_id 꺼냄
     └─ ExchangeRequest.status = "confirmed"
     └─ ChatSession.pending_action = None
     └─ 챗봇: "교환 신청이 완료됐습니다."

사용자: "아니요, 취소할게요"
  → LLM: cancel_pending_action()
     └─ ExchangeRequest.status = "cancelled"
     └─ ChatSession.pending_action = None
     └─ 챗봇: "취소됐습니다."
```

**DB 관련 모델**: `ExchangeRequest` (`shop_exchange_requests`), `ChatSession.pending_action` (Text, JSON)

## 보안 주의

`get_order_status` 도구 실행 시 LLM이 생성한 `user_id`는 무시하고, 서버 세션의 `user_id`를 강제 주입합니다.
