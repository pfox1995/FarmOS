"""Chatbot router."""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.chat_log import ChatLog
from app.models.chat_session import ChatSession
from app.schemas.chatlog import ChatQuestion, ChatAnswer, ChatLogResponse, ChatRating
from app.schemas.chat_session import ChatSessionCreate, ChatSessionResponse, ChatSessionMessages
from app.services.agent_chatbot import AgentChatbotService
from app.farmos_auth import get_farmos_user_optional, FarmOSUser
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])

_chatbot_service_instance: Optional[AgentChatbotService] = None


def set_chatbot_service(service: AgentChatbotService) -> None:
    """앱 시작 시 lifespan에서 싱글턴 서비스를 주입합니다."""
    global _chatbot_service_instance
    _chatbot_service_instance = service


def _get_chatbot_service() -> AgentChatbotService:
    if _chatbot_service_instance is None:
        raise RuntimeError("Chatbot service not initialized. Check app startup.")
    return _chatbot_service_instance


def _resolve_shop_user_id(farmos_user: FarmOSUser, db: Session) -> int:
    """FarmOS JWT 사용자를 쇼핑몰 DB 사용자로 매핑 (없으면 생성)."""
    user = db.query(User).filter(User.user_id == farmos_user.user_id).first()
    if not user:
        user = User(user_id=farmos_user.user_id, name=farmos_user.name)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user.id


def _get_current_user_id(
    request: Request,
    db: Session = Depends(get_db),
) -> int:
    """JWT 쿠키에서 인증된 사용자 ID를 반환. 미인증 시 401."""
    farmos_user = get_farmos_user_optional(request)
    if farmos_user:
        return _resolve_shop_user_id(farmos_user, db)
    raise HTTPException(status_code=401, detail="FarmOS 로그인이 필요합니다.")


def _get_current_user_id_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> int | None:
    """JWT 쿠키에서 인증된 사용자 ID를 반환. 미인증이면 None (게스트 허용)."""
    farmos_user = get_farmos_user_optional(request)
    if farmos_user:
        return _resolve_shop_user_id(farmos_user, db)
    return None


@router.post("/ask", response_model=ChatAnswer)
async def ask_question(
    body: ChatQuestion,
    authenticated_user_id: int | None = Depends(_get_current_user_id_optional),
    db: Session = Depends(get_db),
    debug: bool = Query(False, description="true 시 추론 trace 포함 반환"),
):
    """Submit a question to the AI chatbot."""
    # Guest request: no session validation needed
    if body.session_id is None:
        service = _get_chatbot_service()
        history = [h.model_dump() for h in body.history] if body.history else []
        result = await service.answer(
            db,
            question=body.question,
            user_id=None,
            history=history,
            session_id=None,
        )
        return _build_answer(result, debug)

    # 세션 요청 시 로그인 필수
    if not authenticated_user_id:
        raise HTTPException(status_code=401, detail="세션 사용은 로그인이 필요합니다.")

    # Authenticated request: validate that the session exists and belongs to the authenticated user
    session = db.query(ChatSession).filter(ChatSession.id == body.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if session.user_id != authenticated_user_id:
        raise HTTPException(status_code=403, detail="Cannot access other users' sessions")

    service = _get_chatbot_service()
    history = [h.model_dump() for h in body.history] if body.history else []
    result = await service.answer(
        db,
        question=body.question,
        user_id=authenticated_user_id,
        history=history,
        session_id=body.session_id,
    )
    return _build_answer(result, debug)


def _build_answer(result: dict, debug: bool) -> ChatAnswer:
    from app.schemas.chatlog import TraceStepSchema
    trace = None
    if debug and result.get("trace"):
        trace = [
            TraceStepSchema(
                tool=s.tool,
                arguments=s.arguments,
                result=s.result,
                iteration=s.iteration,
            )
            for s in result["trace"]
        ]
    return ChatAnswer(
        answer=result["answer"],
        intent=result["intent"],
        escalated=result["escalated"],
        trace=trace,
    )


@router.get("/history")
def get_user_history(
    authenticated_user_id: int = Depends(_get_current_user_id),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """회원의 최근 대화 내역을 messages 형태로 반환."""
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == authenticated_user_id)
        .order_by(ChatLog.created_at.desc())
        .limit(limit)
        .all()
    )
    # Reverse to get chronological order (newest first, but each message pair in order)
    logs = list(reversed(logs))
    messages = []
    for log in logs:
        messages.append({"role": "user", "text": log.question})
        messages.append({"role": "bot", "text": log.answer, "intent": log.intent, "escalated": log.escalated})
    return messages


@router.get("/logs", response_model=List[ChatLogResponse])
def list_chat_logs(
    user_id: Optional[int] = Query(None),
    intent: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    authenticated_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """List chat logs with optional filters. 자신의 로그만 조회 가능."""
    query = db.query(ChatLog).filter(ChatLog.user_id == authenticated_user_id)
    if intent:
        query = query.filter(ChatLog.intent == intent)
    return query.order_by(ChatLog.created_at.desc()).limit(limit).all()


@router.get("/logs/escalated", response_model=List[ChatLogResponse])
def list_escalated_logs(
    authenticated_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """List only escalated chat logs for the current user."""
    return (
        db.query(ChatLog)
        .filter(ChatLog.user_id == authenticated_user_id, ChatLog.escalated.is_(True))
        .order_by(ChatLog.created_at.desc())
        .all()
    )


@router.put("/logs/{log_id}/rating", response_model=ChatLogResponse)
def rate_chat_log(
    log_id: int,
    body: ChatRating,
    authenticated_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """Rate a chatbot answer."""
    log = db.query(ChatLog).filter(ChatLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Chat log not found")
    if log.user_id != authenticated_user_id:
        raise HTTPException(status_code=403, detail="다른 사용자의 로그에 별점을 남길 수 없습니다.")
    log.rating = body.rating
    db.commit()
    db.refresh(log)
    return log


# ===== Session Management Endpoints =====


@router.post("/sessions", response_model=ChatSessionResponse)
def create_session(body: ChatSessionCreate, authenticated_user_id: int = Depends(_get_current_user_id), db: Session = Depends(get_db)):
    """Create a new chat session for a user. Only one active session per user allowed."""
    # Validate that user can only create sessions for themselves
    if body.user_id != authenticated_user_id:
        raise HTTPException(status_code=403, detail="Cannot create session for other users")

    # Check if user already has an active session
    existing_active = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == body.user_id, ChatSession.status == "active")
        .first()
    )

    # Close existing active session and create new session in a single transaction
    try:
        # If there's an existing active session, close it
        if existing_active:
            existing_active.status = "closed"
            existing_active.closed_at = datetime.now(timezone.utc)

        # Create new session
        session = ChatSession(user_id=body.user_id, status="active")
        db.add(session)
        db.flush()

        # Add welcome message to chat log
        welcome_log = ChatLog(
            user_id=body.user_id,
            session_id=session.id,
            intent="greeting",
            question="채팅 시작",
            answer="안녕하세요! FarmOS 마켓 고객지원입니다.\n무엇이든 물어보세요 😊",
            escalated=False,
        )
        db.add(welcome_log)
        db.commit()
    except IntegrityError:
        # Race condition: another request created active session simultaneously
        # Rollback and fetch the existing active session instead
        db.rollback()
        existing_session = (
            db.query(ChatSession)
            .filter(ChatSession.user_id == body.user_id, ChatSession.status == "active")
            .first()
        )
        if existing_session:
            session = existing_session
        else:
            # Fallback: shouldn't happen, but retry once more
            raise HTTPException(
                status_code=500,
                detail="Failed to create or retrieve active chat session",
            )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create chat session: {str(e)}")

    db.refresh(session)

    # Build response with preview (same logic as list_sessions)
    session_response = ChatSessionResponse.model_validate(session)

    # Get message count
    message_count = db.query(ChatLog).filter(ChatLog.session_id == session.id).count()
    session_response.message_count = message_count

    # Get the last message for preview (should be the welcome message)
    last_log = (
        db.query(ChatLog)
        .filter(ChatLog.session_id == session.id)
        .order_by(ChatLog.created_at.desc())
        .first()
    )
    if last_log:
        session_response.message_preview = last_log.answer

    return session_response


@router.get("/sessions", response_model=List[ChatSessionResponse])
def list_sessions(
    user_id: int = Query(...),
    authenticated_user_id: int = Depends(_get_current_user_id),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all chat sessions for a user, ordered by most recent first."""
    if user_id != authenticated_user_id:
        raise HTTPException(status_code=403, detail="Cannot access other users' sessions")

    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for session in sessions:
        session_dict = ChatSessionResponse.model_validate(session)
        # Count messages in this session
        message_count = db.query(ChatLog).filter(ChatLog.session_id == session.id).count()
        session_dict.message_count = message_count

        # Get the last message for preview
        last_log = (
            db.query(ChatLog)
            .filter(ChatLog.session_id == session.id)
            .order_by(ChatLog.created_at.desc())
            .first()
        )
        if last_log:
            # Use the bot's answer as preview (more recent in the conversation)
            session_dict.message_preview = last_log.answer

        results.append(session_dict)

    return results


@router.get("/sessions/active", response_model=Optional[ChatSessionResponse])
def get_active_session(
    user_id: int = Query(...),
    authenticated_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get the user's active session if one exists."""
    if user_id != authenticated_user_id:
        raise HTTPException(status_code=403, detail="Cannot access other users' sessions")

    session = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id, ChatSession.status == "active")
        .first()
    )

    if not session:
        return None

    # Enrich response with message_count and message_preview (matching list_sessions logic)
    session_response = ChatSessionResponse.model_validate(session)

    # Count messages in this session
    message_count = db.query(ChatLog).filter(ChatLog.session_id == session.id).count()
    session_response.message_count = message_count

    # Get the last message for preview
    last_log = (
        db.query(ChatLog)
        .filter(ChatLog.session_id == session.id)
        .order_by(ChatLog.created_at.desc())
        .first()
    )
    if last_log:
        session_response.message_preview = last_log.answer

    return session_response


@router.post("/sessions/{session_id}/close", response_model=ChatSessionResponse)
def close_session(
    session_id: int,
    authenticated_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """Close a chat session."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    if session.user_id != authenticated_user_id:
        raise HTTPException(status_code=403, detail="Cannot close other users' sessions")

    # 대기 중인 교환 신청이 있으면 자동 취소
    if session.pending_action:
        try:
            from app.models.exchange_request import ExchangeRequest
            action = json.loads(session.pending_action)
            if action.get("type") == "exchange_request":
                exchange = db.query(ExchangeRequest).filter(
                    ExchangeRequest.id == action["exchange_request_id"],
                    ExchangeRequest.status == "pending_confirm",
                ).first()
                if exchange:
                    exchange.status = "cancelled"
                    db.add(exchange)
        except Exception:
            logger.exception("세션 종료 시 pending_action 정리 실패 (session_id=%s)", session_id)
        session.pending_action = None

    session.status = "closed"
    session.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    authenticated_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """Delete a chat session and all its chat logs."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    if session.user_id != authenticated_user_id:
        raise HTTPException(status_code=403, detail="Cannot delete other users' sessions")

    # Delete all chat logs for this session
    db.query(ChatLog).filter(ChatLog.session_id == session_id).delete()
    # Delete the session
    db.delete(session)
    db.commit()

    return {"message": "Session deleted successfully"}


@router.get("/sessions/{session_id}/messages", response_model=List[ChatSessionMessages])
def get_session_messages(
    session_id: int,
    authenticated_user_id: int = Depends(_get_current_user_id),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get all messages in a chat session."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    if session.user_id != authenticated_user_id:
        raise HTTPException(status_code=403, detail="Cannot access other users' sessions")

    logs = (
        db.query(ChatLog)
        .filter(ChatLog.session_id == session_id)
        .order_by(ChatLog.created_at.desc())
        .limit(limit)
        .all()
    )
    # Reverse to get chronological order (newest first, but each message pair in order)
    logs = list(reversed(logs))

    messages = []
    for log in logs:
        messages.append(
            ChatSessionMessages(
                role="user",
                text=log.question,
                created_at=log.created_at,
            )
        )
        messages.append(
            ChatSessionMessages(
                role="bot",
                text=log.answer,
                intent=log.intent,
                escalated=log.escalated,
                created_at=log.created_at,
            )
        )

    return messages
