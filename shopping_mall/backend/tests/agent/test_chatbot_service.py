"""AgentChatbotService 테스트 — 서비스 레이어 + close_session 라우터."""
import json
from unittest.mock import MagicMock, patch

import pytest

from ai.agent import AgentExecutor, AgentResult
from app.services.agent_chatbot import AgentChatbotService
from tests.conftest import FakeAgentClient, FakeRAGService, make_mock_db, make_text_response

SYSTEM = "당신은 파미입니다."


def make_service(responses=None):
    from ai.agent import TOOL_DEFINITIONS
    client = FakeAgentClient(responses or [make_text_response("테스트 응답")])
    executor = AgentExecutor(
        primary=client,
        fallback=None,
        rag_service=FakeRAGService(),
        tools=TOOL_DEFINITIONS,
    )
    return AgentChatbotService(executor=executor, system_prompt=SYSTEM)


# ══════════════════════════════════════════════════════════════════
# 반환 스키마
# ══════════════════════════════════════════════════════════════════

class TestReturnSchema:

    async def test_answer_returns_required_keys(self):
        """answer() 반환값에 answer/intent/escalated 키 포함."""
        db = make_mock_db()
        service = make_service()

        result = await service.answer(db=db, question="안녕하세요")

        assert "answer" in result
        assert "intent" in result
        assert "escalated" in result

    async def test_answer_is_non_empty_string(self):
        """answer 값이 비어 있지 않은 문자열."""
        db = make_mock_db()
        service = make_service([make_text_response("반갑습니다!")])

        result = await service.answer(db=db, question="안녕")

        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0

    async def test_escalated_is_bool(self):
        """escalated 값이 bool 타입."""
        db = make_mock_db()
        service = make_service()

        result = await service.answer(db=db, question="테스트")

        assert isinstance(result["escalated"], bool)


# ══════════════════════════════════════════════════════════════════
# DB 저장 검증
# ══════════════════════════════════════════════════════════════════

class TestDatabaseSaving:

    async def test_chatlog_is_saved(self):
        """ChatLog가 DB에 add + commit 되는지 확인."""
        db = make_mock_db()
        service = make_service()

        await service.answer(db=db, question="배송 조회", session_id=None)

        db.add.assert_called_once()
        db.commit.assert_called()

    async def test_chatlog_contains_question(self):
        """저장된 ChatLog의 question 필드가 원본 질문과 일치."""
        db = make_mock_db()
        service = make_service()

        await service.answer(db=db, question="딸기 재고 있어?")

        saved_log = db.add.call_args[0][0]
        assert saved_log.question == "딸기 재고 있어?"

    async def test_chatlog_escalated_matches_result(self):
        """ChatLog.escalated가 AgentResult.escalated와 일치."""
        from ai.agent.clients.base import ToolCall
        from tests.conftest import make_tool_response

        db = make_mock_db()
        service = make_service([
            make_tool_response(("escalate_to_agent", {"reason": "요청"})),
            make_text_response("상담원 연결합니다."),
        ])

        await service.answer(db=db, question="상담원 연결")

        saved_log = db.add.call_args[0][0]
        assert saved_log.escalated is True

    async def test_session_title_set_on_first_message(self):
        """세션 제목이 없을 때 첫 질문으로 설정."""
        session = MagicMock()
        session.title = None
        session.updated_at = None

        db = make_mock_db(chat_session=session)
        service = make_service()
        question = "딸기 보관법 알려주세요"

        await service.answer(db=db, question=question, session_id=1)

        assert session.title == question[:50]

    async def test_session_title_not_overwritten(self):
        """이미 제목이 있으면 덮어쓰지 않음."""
        session = MagicMock()
        session.title = "기존 제목"
        session.updated_at = None

        db = make_mock_db(chat_session=session)
        service = make_service()

        await service.answer(db=db, question="새 질문", session_id=1)

        assert session.title == "기존 제목"

    async def test_session_updated_at_is_refreshed(self):
        """answer() 호출 시 session.updated_at이 갱신됨."""
        session = MagicMock()
        session.title = "기존"
        original_updated_at = session.updated_at

        db = make_mock_db(chat_session=session)
        service = make_service()
        await service.answer(db=db, question="테스트", session_id=1)

        # updated_at이 새로운 값으로 설정됐는지 확인 (MagicMock은 set이 기록됨)
        assert session.updated_at is not original_updated_at


# ══════════════════════════════════════════════════════════════════
# history 변환
# ══════════════════════════════════════════════════════════════════

class TestHistoryConversion:

    async def test_empty_history_allowed(self):
        """history=None 또는 []일 때 오류 없이 실행."""
        db = make_mock_db()
        service = make_service([make_text_response("응답1"), make_text_response("응답2")])

        result = await service.answer(db=db, question="안녕", history=None)
        assert result["answer"]

        result = await service.answer(db=db, question="안녕", history=[])
        assert result["answer"]

    async def test_history_role_content_format_passed_through(self):
        """role/content 형식의 history가 LLM messages에 전달됨."""
        from tests.conftest import FakeAgentClient
        from ai.agent import TOOL_DEFINITIONS

        client = FakeAgentClient([make_text_response("기억합니다.")])
        executor = AgentExecutor(
            primary=client,
            fallback=None,
            rag_service=FakeRAGService(),
            tools=TOOL_DEFINITIONS,
        )
        service = AgentChatbotService(executor=executor, system_prompt=SYSTEM)
        db = make_mock_db()

        history = [
            {"role": "user", "content": "이전 질문"},
            {"role": "assistant", "content": "이전 답변"},
        ]

        await service.answer(db=db, question="기억해?", history=history)

        # LLM에 전달된 messages에 history가 포함됐는지 확인
        all_messages = client.calls[0]
        roles = [m["role"] for m in all_messages]
        assert roles.count("user") >= 2      # history의 user + 현재 질문
        assert "assistant" in roles

    async def test_history_window_limited(self):
        """긴 히스토리가 HISTORY_WINDOW_SIZE(6)로 잘림."""
        from tests.conftest import FakeAgentClient
        from ai.agent import TOOL_DEFINITIONS

        client = FakeAgentClient([make_text_response("응.")])
        executor = AgentExecutor(
            primary=client,
            fallback=None,
            rag_service=FakeRAGService(),
            tools=TOOL_DEFINITIONS,
        )
        service = AgentChatbotService(executor=executor, system_prompt=SYSTEM)
        db = make_mock_db()

        # 히스토리 20턴 (user/assistant 각 10개)
        long_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"메시지 {i}"}
            for i in range(20)
        ]

        await service.answer(db=db, question="현재 질문", history=long_history)

        all_messages = client.calls[0]
        # HISTORY_WINDOW_SIZE=6 + 현재 질문 1개 = 7개 이하
        assert len(all_messages) <= 7

    async def test_legacy_text_key_in_history(self):
        """구 형식 history의 'text' 키도 content로 변환됨."""
        from tests.conftest import FakeAgentClient
        from ai.agent import TOOL_DEFINITIONS

        client = FakeAgentClient([make_text_response("응.")])
        executor = AgentExecutor(
            primary=client,
            fallback=None,
            rag_service=FakeRAGService(),
            tools=TOOL_DEFINITIONS,
        )
        service = AgentChatbotService(executor=executor, system_prompt=SYSTEM)
        db = make_mock_db()

        # text 키 사용 (구 형식)
        history = [{"role": "user", "text": "이전 질문"}]

        # 오류 없이 실행되어야 함
        result = await service.answer(db=db, question="현재", history=history)
        assert result["answer"]


# ══════════════════════════════════════════════════════════════════
# close_session 라우터 — pending_action 자동 취소
# ══════════════════════════════════════════════════════════════════

def _make_session(session_id: int, user_id: int, pending_action: str | None = None):
    """ChatSession 목 오브젝트 생성."""
    session = MagicMock()
    session.id = session_id
    session.user_id = user_id
    session.pending_action = pending_action
    return session


def _make_exchange(exchange_id: int, user_id: int, status: str = "pending_confirm"):
    """ExchangeRequest 목 오브젝트 생성."""
    ex = MagicMock()
    ex.id = exchange_id
    ex.user_id = user_id
    ex.status = status
    return ex


def _make_db_for_close(session, exchange=None):
    """close_session 테스트용 DB 목."""
    from app.models.chat_session import ChatSession
    from app.models.exchange_request import ExchangeRequest

    db = MagicMock()
    session_mock = MagicMock()
    exchange_mock = MagicMock()

    def query_side_effect(model):
        if model is ChatSession:
            return session_mock
        if model is ExchangeRequest:
            return exchange_mock
        return MagicMock()

    db.query.side_effect = query_side_effect
    session_mock.filter.return_value.first.return_value = session
    exchange_mock.filter.return_value.first.return_value = exchange
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    return db


class TestCloseSessionPendingAction:

    def test_pending_confirm_exchange_cancelled_on_close(self):
        """세션 종료 시 pending_confirm 교환 신청이 cancelled로 변경."""
        from app.routers.chatbot import close_session

        exchange = _make_exchange(exchange_id=42, user_id=1)
        pending = json.dumps({"type": "exchange_request", "exchange_request_id": 42})
        session = _make_session(session_id=10, user_id=1, pending_action=pending)
        db = _make_db_for_close(session, exchange=exchange)

        close_session(session_id=10, authenticated_user_id=1, db=db)

        assert exchange.status == "cancelled"
        db.add.assert_any_call(exchange)
        db.commit.assert_called()

    def test_no_pending_action_closes_normally(self):
        """pending_action이 없는 세션도 정상 종료."""
        from app.routers.chatbot import close_session

        session = _make_session(session_id=10, user_id=1, pending_action=None)
        db = _make_db_for_close(session)

        close_session(session_id=10, authenticated_user_id=1, db=db)

        assert session.status == "closed"
        db.commit.assert_called()

    def test_invalid_json_pending_action_still_closes(self):
        """pending_action JSON 파싱 실패 시에도 세션은 정상 종료."""
        from app.routers.chatbot import close_session

        session = _make_session(session_id=10, user_id=1, pending_action="invalid-json{{{")
        db = _make_db_for_close(session)

        # 예외 없이 실행되어야 함
        close_session(session_id=10, authenticated_user_id=1, db=db)

        assert session.status == "closed"
        db.commit.assert_called()
