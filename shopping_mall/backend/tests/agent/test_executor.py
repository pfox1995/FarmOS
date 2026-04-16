"""AgentExecutor 테스트 — 정상 케이스 & 실패 케이스."""
import json
import pytest
from unittest.mock import MagicMock, patch

from ai.agent import AgentUnavailableError, AgentExecutor
from tests.conftest import (
    FakeAgentClient,
    FakeRAGService,
    make_mock_db,
    make_order,
    make_shipment,
    make_product,
    make_text_response,
    make_tool_response,
)


def make_hitl_db(order=None, session=None, exchange=None):
    """HitL 도구(create/confirm/cancel_exchange_request)용 DB 목.

    Order/ChatSession/ExchangeRequest 모두 .filter().first() 체인만 지원.
    """
    from app.models.order import Order
    from app.models.chat_session import ChatSession
    from app.models.exchange_request import ExchangeRequest

    db = MagicMock()
    order_mock = MagicMock()
    session_mock = MagicMock()
    exchange_mock = MagicMock()

    def query_side_effect(model):
        if model is Order:
            return order_mock
        if model is ChatSession:
            return session_mock
        if model is ExchangeRequest:
            return exchange_mock
        return MagicMock()

    db.query.side_effect = query_side_effect
    order_mock.filter.return_value.first.return_value = order
    session_mock.filter.return_value.first.return_value = session
    exchange_mock.filter.return_value.first.return_value = exchange
    db.add = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


def make_hitl_session(session_id=1, pending_action=None):
    """ChatSession 목 — HitL 테스트 전용."""
    s = MagicMock()
    s.id = session_id
    s.pending_action = pending_action
    return s


def make_hitl_exchange(exchange_id=42, user_id=10, status="pending_confirm"):
    """ExchangeRequest 목 — HitL 테스트 전용."""
    ex = MagicMock()
    ex.id = exchange_id
    ex.user_id = user_id
    ex.status = status
    return ex

SYSTEM = "당신은 파미입니다."


def make_executor(primary, fallback=None, rag=None, max_iterations=10):
    from ai.agent.tools import TOOL_DEFINITIONS
    return AgentExecutor(
        primary=primary,
        fallback=fallback,
        rag_service=rag or FakeRAGService(),
        tools=TOOL_DEFINITIONS,
        max_iterations=max_iterations,
    )


# ══════════════════════════════════════════════════════════════════
# 정상 케이스
# ══════════════════════════════════════════════════════════════════

class TestNormalCases:

    async def test_direct_text_answer(self, empty_db):
        """도구 호출 없이 LLM이 직접 텍스트로 답변."""
        client = FakeAgentClient([
            make_text_response("안녕하세요! 무엇을 도와드릴까요?"),
        ])
        executor = make_executor(client)

        result = await executor.run(empty_db, "안녕하세요", None, [], SYSTEM)

        assert result.answer == "안녕하세요! 무엇을 도와드릴까요?"
        assert result.tools_used == []
        assert result.intent == "other"
        assert result.escalated is False
        assert len(client.calls) == 1

    async def test_single_tool_then_answer(self, empty_db):
        """단일 도구 호출 후 최종 답변."""
        client = FakeAgentClient([
            make_tool_response(("search_products", {"query": "딸기"})),
            make_text_response("딸기는 현재 150개 재고가 있습니다."),
        ])
        rag = FakeRAGService()
        executor = make_executor(client, rag=rag)

        result = await executor.run(empty_db, "딸기 재고 있어?", None, [], SYSTEM)

        assert "딸기" in result.answer
        assert result.tools_used == ["search_products"]
        assert result.intent == "stock"
        assert result.escalated is False
        assert len(client.calls) == 2

    async def test_multi_tool_sequence(self, empty_db):
        """두 개 도구를 순차 호출 후 최종 답변 (복합 질문)."""
        client = FakeAgentClient([
            make_tool_response(("search_products", {"query": "딸기"})),
            make_tool_response(("search_storage_guide", {"product_name": "딸기", "query": "딸기 보관법"})),
            make_text_response("딸기는 150개 재고가 있으며, 냉장 보관하시면 됩니다."),
        ])
        rag = FakeRAGService({"storage_guide": ["딸기는 냉장 보관하세요."]})
        executor = make_executor(client, rag=rag)

        result = await executor.run(empty_db, "딸기 재고랑 보관법 알려줘", None, [], SYSTEM)

        assert result.tools_used == ["search_products", "search_storage_guide"]
        assert result.intent == "stock"      # 첫 번째 도구 기준
        assert result.escalated is False
        assert len(client.calls) == 3

    async def test_parallel_tool_calls_in_one_turn(self, empty_db):
        """한 턴에 여러 도구를 동시에 호출."""
        client = FakeAgentClient([
            make_tool_response(
                ("search_products", {"query": "사과"}),
                ("search_faq", {"query": "배송 기간"}),
            ),
            make_text_response("사과 재고 확인 및 배송 안내 드립니다."),
        ])
        executor = make_executor(client)

        result = await executor.run(empty_db, "사과 있어요? 배송은 얼마나 걸려요?", None, [], SYSTEM)

        assert set(result.tools_used) == {"search_products", "search_faq"}
        assert len(client.calls) == 2

    async def test_rag_docs_passed_to_llm(self, empty_db):
        """RAG 검색 결과가 tool_result로 LLM에 전달되는지 검증."""
        policy_doc = "반품은 수령 후 24시간 이내 신청 가능합니다."
        client = FakeAgentClient([
            make_tool_response(("search_policy", {"query": "반품 기간", "policy_type": "return"})),
            make_text_response("반품은 수령 후 24시간 이내 가능합니다."),
        ])
        rag = FakeRAGService({"return_policy": [policy_doc]})
        executor = make_executor(client, rag=rag)

        await executor.run(empty_db, "반품 얼마나 기다려요?", None, [], SYSTEM)

        # 두 번째 LLM 호출 messages에 policy_doc이 포함돼야 함
        second_call_messages = client.calls[1]
        all_content = " ".join(
            m.get("content", "") if isinstance(m.get("content"), str) else ""
            for m in second_call_messages
        )
        assert policy_doc in all_content

    async def test_get_order_status_logged_in(self):
        """로그인 사용자의 주문/배송 조회."""
        order = make_order(order_id=100, user_id=10, status="shipping")
        shipment = make_shipment(order_id=100, carrier="CJ대한통운", tracking_number="9999")
        db = make_mock_db(orders=[order], shipments=[shipment])

        client = FakeAgentClient([
            make_tool_response(("get_order_status", {"user_id": 10})),
            make_text_response("주문 #100이 배송 중입니다. CJ대한통운 9999번으로 조회하세요."),
        ])
        executor = make_executor(client)

        result = await executor.run(db, "내 배송 어디까지 왔어요?", user_id=10, history=[], system=SYSTEM)

        assert result.tools_used == ["get_order_status"]
        assert result.intent == "delivery"
        assert result.escalated is False

    async def test_get_order_status_result_contains_tracking(self):
        """도구 결과에 송장번호가 포함되는지 직접 검증."""
        order = make_order(order_id=55, user_id=7, status="shipping")
        shipment = make_shipment(tracking_number="TRK-001", carrier="한진택배")
        db = make_mock_db(orders=[order], shipments=[shipment])

        executor = make_executor(FakeAgentClient([
            make_tool_response(("get_order_status", {"user_id": 7})),
            make_text_response("배송 중입니다."),
        ]))

        # 도구를 직접 호출하여 결과 검증
        from ai.agent.clients.base import ToolCall
        tc = ToolCall(id="t1", name="get_order_status", arguments={"user_id": 7})
        raw = await executor._dispatch_tool(tc, db, user_id=7)

        assert "TRK-001" in raw
        assert "한진택배" in raw

    async def test_search_products_returns_formatted_list(self, empty_db):
        """상품 검색 도구가 형식화된 문자열을 반환."""
        product = make_product(product_id=3, name="유기농 딸기", price=15000, stock=80)
        db = make_mock_db(products=[product])

        executor = make_executor(FakeAgentClient([
            make_tool_response(("search_products", {"query": "딸기"})),
            make_text_response("유기농 딸기가 있습니다."),
        ]))

        from ai.agent.clients.base import ToolCall
        tc = ToolCall(id="t1", name="search_products", arguments={"query": "딸기"})
        raw = await executor._dispatch_tool(tc, db, user_id=None)

        assert "유기농 딸기" in raw
        assert "15,000" in raw
        assert "재고 80개" in raw

    async def test_history_appended_to_messages(self, empty_db):
        """이전 대화 히스토리가 LLM 호출에 포함되는지 검증."""
        client = FakeAgentClient([make_text_response("네, 기억합니다.")])
        executor = make_executor(client)
        history = [
            {"role": "user", "content": "딸기 있어요?"},
            {"role": "assistant", "content": "딸기는 150개 재고가 있습니다."},
        ]

        await executor.run(empty_db, "아까 말한 거 기억해?", None, history, SYSTEM)

        first_call = client.calls[0]
        roles = [m["role"] for m in first_call]
        assert "user" in roles
        assert "assistant" in roles

    async def test_escalate_to_agent_sets_flag(self, empty_db):
        """escalate_to_agent 도구 호출 시 escalated=True."""
        client = FakeAgentClient([
            make_tool_response(("escalate_to_agent", {"reason": "고객 요청", "urgency": "normal"})),
            make_text_response("상담원에게 연결해 드리겠습니다."),
        ])
        executor = make_executor(client)

        result = await executor.run(empty_db, "상담원 연결해주세요", None, [], SYSTEM)

        assert result.escalated is True
        assert result.intent == "escalation"

    async def test_escalate_high_urgency_message(self, empty_db):
        """urgency=high 에스컬레이션 메시지에 '우선 처리' 포함."""
        from ai.agent.clients.base import ToolCall
        executor = make_executor(FakeAgentClient([]))

        tc = ToolCall(id="t1", name="escalate_to_agent", arguments={"reason": "긴급", "urgency": "high"})
        raw = await executor._dispatch_tool(tc, empty_db, user_id=None)

        assert "우선" in raw or "빠르게" in raw

    async def test_search_policy_all_types(self):
        """policy_type=all 시 여러 컬렉션에서 통합 검색."""
        from ai.agent.clients.base import ToolCall

        rag = FakeRAGService({
            "return_policy": ["반품 정책 내용"],
            "payment_policy": ["결제 정책 내용"],
        })
        executor = make_executor(FakeAgentClient([]), rag=rag)
        db = make_mock_db()

        tc = ToolCall(id="t1", name="search_policy", arguments={"query": "환불", "policy_type": "all"})
        raw = await executor._dispatch_tool(tc, db, user_id=None)

        assert "반품 정책 내용" in raw
        assert "결제 정책 내용" in raw


# ══════════════════════════════════════════════════════════════════
# 실패 케이스
# ══════════════════════════════════════════════════════════════════

class TestFailureCases:

    async def test_ollama_fails_claude_takes_over(self, empty_db):
        """Primary(Ollama) 실패 시 Fallback(Claude)이 응답."""
        primary = FakeAgentClient([AgentUnavailableError("Ollama 서버 오프라인")])
        fallback = FakeAgentClient([make_text_response("Claude 폴백 응답입니다.")])
        executor = make_executor(primary, fallback=fallback)

        result = await executor.run(empty_db, "안녕", None, [], SYSTEM)

        assert result.answer == "Claude 폴백 응답입니다."
        assert result.escalated is False
        assert len(primary.calls) == 1      # primary는 1회 시도
        assert len(fallback.calls) == 1     # fallback이 처리

    async def test_both_llm_fail_returns_error_message(self, empty_db):
        """Primary + Fallback 모두 실패 시 에러 메시지 + escalated=True."""
        primary = FakeAgentClient([AgentUnavailableError("Ollama 오프라인")])
        fallback = FakeAgentClient([AgentUnavailableError("Claude API 오류")])
        executor = make_executor(primary, fallback=fallback)

        result = await executor.run(empty_db, "주문 조회", None, [], SYSTEM)

        assert result.escalated is True
        assert "오류" in result.answer or "문제" in result.answer or "센터" in result.answer

    async def test_no_fallback_configured_ollama_fails(self, empty_db):
        """Fallback 없이 Primary 실패 시 에러 메시지."""
        primary = FakeAgentClient([AgentUnavailableError("연결 불가")])
        executor = make_executor(primary, fallback=None)

        result = await executor.run(empty_db, "배송 조회", None, [], SYSTEM)

        assert result.escalated is True
        assert result.answer  # 빈 문자열이 아닌 에러 안내 메시지

    async def test_max_iterations_exceeded(self, empty_db):
        """10회 반복 후에도 도구만 호출하면 에스컬레이션."""
        # 항상 tool_call만 반환 (텍스트 없음)
        infinite_tools = [
            make_tool_response(("search_faq", {"query": "test"}))
            for _ in range(15)
        ]
        client = FakeAgentClient(infinite_tools)
        executor = make_executor(client, max_iterations=3)

        result = await executor.run(empty_db, "뭔가 물어봐", None, [], SYSTEM)

        assert result.escalated is True
        assert len(client.calls) == 3      # max_iterations=3회만 호출

    async def test_tool_error_is_handled_gracefully(self, empty_db):
        """도구 실행 중 예외가 발생해도 루프가 계속되고 오류 메시지를 LLM에 전달."""
        client = FakeAgentClient([
            make_tool_response(("search_products", {"query": "딸기"})),
            make_text_response("죄송합니다, 일시적 문제가 있었지만 안내해 드립니다."),
        ])
        # DB를 예외를 던지도록 설정
        bad_db = make_mock_db()
        bad_db.query.side_effect = RuntimeError("DB 연결 실패")

        executor = make_executor(client)

        result = await executor.run(bad_db, "딸기 있어?", None, [], SYSTEM)

        # 루프가 중단되지 않고 LLM이 최종 답변
        assert result.answer
        assert result.escalated is False

    async def test_get_order_status_without_login(self, empty_db):
        """비로그인 사용자가 주문 조회 시 '로그인 필요' 메시지."""
        from ai.agent.clients.base import ToolCall

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="get_order_status", arguments={"user_id": 999})

        raw = await executor._dispatch_tool(tc, empty_db, user_id=None)

        assert "로그인" in raw

    async def test_get_order_status_user_id_injection_security(self):
        """LLM이 임의 user_id를 전달해도 서버 세션의 user_id(7)만 사용."""
        SESSION_USER_ID = 7
        ATTACKER_USER_ID = 999

        # user_id=7의 주문만 존재
        order = make_order(order_id=10, user_id=SESSION_USER_ID)
        shipment = make_shipment(order_id=10)

        # DB 목: user_id 인자 검증을 위해 side_effect 사용
        captured_filters = []

        db = make_mock_db(orders=[order], shipments=[shipment])

        from ai.agent.clients.base import ToolCall
        executor = make_executor(FakeAgentClient([]))

        # LLM이 args에 attacker user_id를 넣었지만 executor에서 pop해야 함
        tc = ToolCall(
            id="t1",
            name="get_order_status",
            arguments={"user_id": ATTACKER_USER_ID, "order_id": None},
        )
        # _dispatch_tool이 args.pop("user_id") 후 SESSION_USER_ID를 주입
        raw = await executor._dispatch_tool(tc, db, user_id=SESSION_USER_ID)

        # SESSION_USER_ID=7의 주문(#10)이 조회되어야 함 — 주입된 user_id=999는 무시
        assert "#10" in raw, f"서버 세션 user_id=7의 주문이 조회되어야 함, 실제 응답: {raw}"

    async def test_get_order_status_no_orders_found(self):
        """조회된 주문이 없을 때 안내 메시지."""
        db = make_mock_db(orders=[])

        from ai.agent.clients.base import ToolCall
        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="get_order_status", arguments={})

        raw = await executor._dispatch_tool(tc, db, user_id=5)

        assert "없" in raw  # "조회된 주문이 없습니다" 등

    async def test_empty_rag_results_returns_fallback(self, empty_db):
        """RAG에 관련 문서가 없을 때 폴백 텍스트 반환."""
        from ai.agent.clients.base import ToolCall

        rag = FakeRAGService()  # 모든 컬렉션 빈 상태
        executor = make_executor(FakeAgentClient([]), rag=rag)

        tc = ToolCall(id="t1", name="search_storage_guide", arguments={"product_name": "희귀버섯", "query": "보관법"})
        raw = await executor._dispatch_tool(tc, empty_db, user_id=None)

        assert "찾을 수 없" in raw or "없습니다" in raw

    async def test_search_products_no_results(self):
        """상품 검색 결과 없을 때 '결과 없음' 메시지."""
        db = make_mock_db(products=[])

        from ai.agent.clients.base import ToolCall
        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="search_products", arguments={"query": "존재하지않는상품XYZ"})

        raw = await executor._dispatch_tool(tc, db, user_id=None)

        assert "없" in raw

    async def test_unknown_tool_name_returns_error(self, empty_db):
        """정의되지 않은 도구명이 오면 오류 메시지 반환."""
        from ai.agent.clients.base import ToolCall

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="nonexistent_tool", arguments={})

        raw = await executor._dispatch_tool(tc, empty_db, user_id=None)

        assert "알 수 없는 도구" in raw or "오류" in raw

    async def test_ollama_fails_mid_loop_fallback_restarts(self, empty_db):
        """Primary가 루프 중간에 실패해도 Fallback이 처음부터 재시도."""
        primary = FakeAgentClient([AgentUnavailableError("타임아웃")])
        fallback = FakeAgentClient([
            make_tool_response(("search_faq", {"query": "배송"})),
            make_text_response("배송은 1-3일 소요됩니다."),
        ])
        executor = make_executor(primary, fallback=fallback)

        result = await executor.run(empty_db, "배송 기간이 어떻게 돼요?", None, [], SYSTEM)

        assert "배송" in result.answer
        assert result.escalated is False
        assert len(fallback.calls) == 2     # fallback이 처음부터 루프 실행


# ══════════════════════════════════════════════════════════════════
# intent 역산 로직
# ══════════════════════════════════════════════════════════════════

class TestIntentMapping:

    @pytest.mark.parametrize("tool_name,expected_intent", [
        ("get_order_status", "delivery"),
        ("search_products", "stock"),
        ("get_product_detail", "stock"),
        ("search_storage_guide", "storage"),
        ("search_season_info", "season"),
        ("search_policy", "policy"),
        ("search_faq", "other"),
        ("search_farm_info", "other"),
        ("escalate_to_agent", "escalation"),
    ])
    async def test_intent_from_tool(self, tool_name, expected_intent, empty_db):
        """각 도구 호출 시 올바른 intent가 역산되는지 검증."""
        args: dict = {"query": "test"}
        if tool_name == "get_order_status":
            args = {"user_id": 1}
        elif tool_name == "search_storage_guide":
            args = {"product_name": "딸기", "query": "보관법"}
        elif tool_name == "get_product_detail":
            args = {"product_name": "딸기"}
        elif tool_name == "escalate_to_agent":
            args = {"reason": "고객 요청"}

        client = FakeAgentClient([
            make_tool_response((tool_name, args)),
            make_text_response("답변입니다."),
        ])
        executor = make_executor(client)

        result = await executor.run(empty_db, "테스트", user_id=1, history=[], system=SYSTEM)

        assert result.intent == expected_intent, (
            f"tool={tool_name}: expected intent={expected_intent}, got={result.intent}"
        )

    async def test_no_tool_used_intent_is_other(self, empty_db):
        """도구 미사용 시 intent='other'."""
        client = FakeAgentClient([make_text_response("직접 답변")])
        result = await make_executor(client).run(empty_db, "안녕", None, [], SYSTEM)
        assert result.intent == "other"


# ══════════════════════════════════════════════════════════════════
# get_product_detail 직접 결과 검증
# ══════════════════════════════════════════════════════════════════

class TestGetProductDetail:

    async def test_by_id_returns_detail(self):
        """product_id로 상품 상세 조회 성공."""
        from ai.agent.clients.base import ToolCall

        product = make_product(product_id=10, name="유기농 사과", price=20000, stock=50)
        db = make_mock_db(products=[product])
        # filter().first() 지원
        from app.models.product import Product
        product_mock = MagicMock()
        product_mock.filter.return_value.first.return_value = product
        db.query.side_effect = lambda m: product_mock if m is Product else MagicMock()

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="get_product_detail", arguments={"product_id": 10})
        raw = await executor._dispatch_tool(tc, db, user_id=None)

        assert "유기농 사과" in raw
        assert "20,000" in raw
        assert "50개 재고" in raw

    async def test_by_name_returns_detail(self):
        """product_name으로 상품 상세 조회 성공."""
        from ai.agent.clients.base import ToolCall
        from app.models.product import Product

        product = make_product(product_id=5, name="제주 감귤", price=8000, stock=200)
        product_mock = MagicMock()
        product_mock.filter.return_value.first.return_value = product
        db = MagicMock()
        db.query.side_effect = lambda m: product_mock if m is Product else MagicMock()

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="get_product_detail", arguments={"product_name": "감귤"})
        raw = await executor._dispatch_tool(tc, db, user_id=None)

        assert "제주 감귤" in raw

    async def test_product_not_found(self):
        """존재하지 않는 상품 조회 시 안내 메시지."""
        from ai.agent.clients.base import ToolCall
        from app.models.product import Product

        product_mock = MagicMock()
        product_mock.filter.return_value.first.return_value = None
        db = MagicMock()
        db.query.side_effect = lambda m: product_mock if m is Product else MagicMock()

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="get_product_detail", arguments={"product_name": "없는상품XYZ"})
        raw = await executor._dispatch_tool(tc, db, user_id=None)

        assert "찾을 수 없" in raw

    async def test_no_args_returns_guidance(self, empty_db):
        """product_id/product_name 모두 없을 때 안내 메시지."""
        from ai.agent.clients.base import ToolCall

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="get_product_detail", arguments={})
        raw = await executor._dispatch_tool(tc, empty_db, user_id=None)

        assert "입력해 주세요" in raw or "ID" in raw

    async def test_out_of_stock_shows_soldout(self):
        """재고 0인 상품에 '품절' 표시."""
        from ai.agent.clients.base import ToolCall
        from app.models.product import Product

        product = make_product(product_id=7, name="품절상품", price=5000, stock=0)
        product.restock_date = None
        product_mock = MagicMock()
        product_mock.filter.return_value.first.return_value = product
        db = MagicMock()
        db.query.side_effect = lambda m: product_mock if m is Product else MagicMock()

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="get_product_detail", arguments={"product_id": 7})
        raw = await executor._dispatch_tool(tc, db, user_id=None)

        assert "품절" in raw


# ══════════════════════════════════════════════════════════════════
# search_products 추가 케이스
# ══════════════════════════════════════════════════════════════════

class TestSearchProductsExtra:

    async def test_check_stock_filters_out_of_stock(self):
        """check_stock=True 시 재고 있는 상품만 반환."""
        from ai.agent.clients.base import ToolCall

        product = make_product(product_id=1, name="딸기", stock=10)
        db = make_mock_db(products=[product])

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="search_products", arguments={"query": "딸기", "check_stock": True})
        raw = await executor._dispatch_tool(tc, db, user_id=None)

        assert "딸기" in raw

    async def test_limit_clamped_at_20(self):
        """limit > 20 시 20으로 clamp — DB에 limit(20) 이하로 호출."""
        from ai.agent.clients.base import ToolCall
        from app.models.product import Product

        products = [make_product(product_id=i, name=f"상품{i}", stock=5) for i in range(25)]
        product_mock = MagicMock()
        captured_limit = []

        def limit_side_effect(n):
            captured_limit.append(n)
            ret = MagicMock()
            ret.all.return_value = products[:n]
            return ret

        product_mock.filter.return_value.order_by.return_value.limit.side_effect = limit_side_effect
        db = MagicMock()
        db.query.side_effect = lambda m: product_mock if m is Product else MagicMock()

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="search_products", arguments={"query": "상품", "limit": 100})
        await executor._dispatch_tool(tc, db, user_id=None)

        assert captured_limit and captured_limit[0] <= 20, (
            f"limit이 {captured_limit[0]}로 호출됨 — 20 이하이어야 함"
        )


# ══════════════════════════════════════════════════════════════════
# Human-in-the-Loop 도구 테스트
# ══════════════════════════════════════════════════════════════════

class TestHumanInTheLoop:

    # ── create_exchange_request ─────────────────────────────────────

    async def test_create_not_logged_in(self, empty_db):
        """비로그인 시 교환 신청 거부."""
        from ai.agent.clients.base import ToolCall

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="create_exchange_request", arguments={"order_id": 1, "reason": "파손"})
        raw = await executor._dispatch_tool(tc, empty_db, user_id=None, session_id=None)

        assert "로그인" in raw

    async def test_create_no_session_id(self):
        """session_id 없이 교환 신청 거부 (세션 없음 메시지)."""
        from ai.agent.clients.base import ToolCall

        db = make_hitl_db()
        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="create_exchange_request", arguments={"order_id": 1, "reason": "파손"})
        raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=None)

        assert "세션" in raw

    async def test_create_order_not_found(self):
        """주문을 찾을 수 없을 때 오류 메시지."""
        from ai.agent.clients.base import ToolCall

        db = make_hitl_db(order=None)
        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="create_exchange_request", arguments={"order_id": 99, "reason": "파손"})
        raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=1)

        assert "찾을 수 없" in raw or "권한" in raw

    async def test_create_wrong_order_status(self):
        """교환 불가 상태(registered)인 주문에 교환 신청 거부."""
        from ai.agent.clients.base import ToolCall

        order = make_order(order_id=5, user_id=10, status="registered")
        db = make_hitl_db(order=order)
        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="create_exchange_request", arguments={"order_id": 5, "reason": "파손"})
        raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=1)

        assert "불가" in raw

    async def test_create_success_delivered(self):
        """배송완료 주문에 교환 신청 성공 — 확인 요청 메시지 반환."""
        from ai.agent.clients.base import ToolCall

        order = make_order(order_id=7, user_id=10, status="delivered")
        session = make_hitl_session(session_id=1)
        db = make_hitl_db(order=order, session=session)

        executor = make_executor(FakeAgentClient([]))

        with patch("app.models.exchange_request.ExchangeRequest") as MockExchange:
            mock_ex = MagicMock()
            mock_ex.id = 42
            MockExchange.return_value = mock_ex

            tc = ToolCall(id="t1", name="create_exchange_request", arguments={"order_id": 7, "reason": "배송 중 파손"})
            raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=1)

        assert "확인" in raw or "교환" in raw
        db.commit.assert_called()

    async def test_create_success_shipping(self):
        """배송중 주문에도 교환 신청 가능."""
        from ai.agent.clients.base import ToolCall

        order = make_order(order_id=8, user_id=10, status="shipping")
        session = make_hitl_session(session_id=2)
        db = make_hitl_db(order=order, session=session)

        executor = make_executor(FakeAgentClient([]))

        with patch("app.models.exchange_request.ExchangeRequest") as MockExchange:
            mock_ex = MagicMock()
            mock_ex.id = 99
            MockExchange.return_value = mock_ex

            tc = ToolCall(id="t1", name="create_exchange_request", arguments={"order_id": 8, "reason": "사이즈 불량"})
            raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=2)

        assert "확인" in raw or "교환" in raw

    # ── confirm_pending_action ─────────────────────────────────────

    async def test_confirm_no_session_id(self, empty_db):
        """session_id 없이 confirm 시 거부."""
        from ai.agent.clients.base import ToolCall

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="confirm_pending_action", arguments={})
        raw = await executor._dispatch_tool(tc, empty_db, user_id=10, session_id=None)

        assert "없습니다" in raw

    async def test_confirm_no_pending_action(self):
        """pending_action이 없는 세션에서 confirm 시 거부."""
        from ai.agent.clients.base import ToolCall

        session = make_hitl_session(session_id=1, pending_action=None)
        db = make_hitl_db(session=session)
        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="confirm_pending_action", arguments={})
        raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=1)

        assert "없습니다" in raw

    async def test_confirm_success(self):
        """pending_confirm 교환 신청 확인 → status=confirmed, pending_action=None."""
        from ai.agent.clients.base import ToolCall

        exchange = make_hitl_exchange(exchange_id=42, user_id=10, status="pending_confirm")
        pending = json.dumps({"type": "exchange_request", "exchange_request_id": 42})
        session = make_hitl_session(session_id=1, pending_action=pending)
        db = make_hitl_db(session=session, exchange=exchange)

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="confirm_pending_action", arguments={})
        raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=1)

        assert exchange.status == "confirmed"
        assert session.pending_action is None
        assert "완료" in raw or "접수번호" in raw
        db.commit.assert_called()

    async def test_confirm_wrong_owner(self):
        """다른 사용자의 교환 신청 — exchange 조회 None → '처리되었거나' 안내."""
        from ai.agent.clients.base import ToolCall

        pending = json.dumps({"type": "exchange_request", "exchange_request_id": 42})
        session = make_hitl_session(session_id=1, pending_action=pending)
        db = make_hitl_db(session=session, exchange=None)  # user_id 불일치 → None

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="confirm_pending_action", arguments={})
        raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=1)

        assert "처리되었거나" in raw or "유효하지 않은" in raw

    # ── cancel_pending_action ──────────────────────────────────────

    async def test_cancel_no_session_id(self, empty_db):
        """session_id 없이 cancel 시 거부."""
        from ai.agent.clients.base import ToolCall

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="cancel_pending_action", arguments={})
        raw = await executor._dispatch_tool(tc, empty_db, user_id=10, session_id=None)

        assert "없습니다" in raw

    async def test_cancel_no_pending_action(self):
        """pending_action이 없는 세션에서 cancel 시 거부."""
        from ai.agent.clients.base import ToolCall

        session = make_hitl_session(session_id=1, pending_action=None)
        db = make_hitl_db(session=session)
        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="cancel_pending_action", arguments={})
        raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=1)

        assert "없습니다" in raw

    async def test_cancel_success(self):
        """pending_confirm 교환 신청 취소 → status=cancelled, pending_action=None."""
        from ai.agent.clients.base import ToolCall

        exchange = make_hitl_exchange(exchange_id=42, user_id=10, status="pending_confirm")
        pending = json.dumps({"type": "exchange_request", "exchange_request_id": 42})
        session = make_hitl_session(session_id=1, pending_action=pending)
        db = make_hitl_db(session=session, exchange=exchange)

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="cancel_pending_action", arguments={})
        raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=1)

        assert exchange.status == "cancelled"
        assert session.pending_action is None
        assert "취소" in raw
        db.commit.assert_called()

    async def test_cancel_wrong_owner_still_clears_session(self):
        """소유권 불일치(exchange=None)여도 세션 pending_action 정리 후 취소 메시지."""
        from ai.agent.clients.base import ToolCall

        pending = json.dumps({"type": "exchange_request", "exchange_request_id": 42})
        session = make_hitl_session(session_id=1, pending_action=pending)
        db = make_hitl_db(session=session, exchange=None)  # user_id 불일치 → None

        executor = make_executor(FakeAgentClient([]))
        tc = ToolCall(id="t1", name="cancel_pending_action", arguments={})
        raw = await executor._dispatch_tool(tc, db, user_id=10, session_id=1)

        assert session.pending_action is None
        assert "취소" in raw
