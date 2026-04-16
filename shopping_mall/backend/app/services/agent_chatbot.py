"""에이전트 기반 챗봇 서비스 — ChatbotService와 동일한 인터페이스."""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ai.agent import AgentExecutor

logger = logging.getLogger(__name__)

HISTORY_WINDOW_SIZE = 6


class AgentChatbotService:
    """AgentExecutor를 래핑하여 기존 ChatbotService.answer() 인터페이스를 구현."""

    def __init__(self, executor: AgentExecutor, system_prompt: str):
        self.executor = executor
        self.system_prompt = system_prompt

    async def answer(
        self,
        db: Session,
        question: str,
        user_id: int | None = None,
        history: list | None = None,
        session_id: int | None = None,
    ) -> dict:
        # history → LLM 메시지 형식 변환 (최근 N턴)
        messages = self._build_history(history)

        # 요청 컨텍스트 생성 (날짜/시각, 로그인 상태)
        from ai.agent import RequestContext
        context = RequestContext.build(user_id)

        # 에이전트 실행
        result = await self.executor.run(
            db=db,
            user_message=question,
            user_id=user_id,
            session_id=session_id,
            history=messages,
            system=self.system_prompt,
            context=context,
        )

        # ChatLog 저장 + 세션 메타데이터 갱신 (단일 트랜잭션)
        from app.models.chat_log import ChatLog
        log = ChatLog(
            user_id=user_id,
            session_id=session_id,
            intent=result.intent,
            question=question,
            answer=result.answer,
            escalated=result.escalated,
        )
        db.add(log)

        if session_id:
            from app.models.chat_session import ChatSession
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session:
                if not session.title:
                    session.title = question[:50]
                session.updated_at = datetime.now(timezone.utc)

        db.commit()

        return {
            "answer": result.answer,
            "intent": result.intent,
            "escalated": result.escalated,
            "trace": result.trace,
        }

    def _build_history(self, history: list | None) -> list[dict]:
        """기존 history 형식 → LLM 메시지 형식 변환."""
        if not history:
            return []

        messages = []
        for item in history[-HISTORY_WINDOW_SIZE:]:
            # 기존 형식: {"role": "user"/"assistant", "content"/"text": str}
            role = item.get("role", "user")
            content = item.get("content") or item.get("text", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        return messages
