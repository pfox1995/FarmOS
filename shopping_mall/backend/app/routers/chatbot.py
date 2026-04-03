"""Chatbot router."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat_log import ChatLog
from app.schemas.chatlog import ChatQuestion, ChatAnswer, ChatLogResponse, ChatRating
from app.services.ai_chatbot import ChatbotService
from ai.llm_client import LLMClient
from ai.rag import RAGService

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])


def _get_chatbot_service() -> ChatbotService:
    llm = LLMClient()
    rag = RAGService(llm_client=llm)
    return ChatbotService(llm_client=llm, rag_service=rag)


@router.post("/ask", response_model=ChatAnswer)
async def ask_question(body: ChatQuestion, db: Session = Depends(get_db)):
    """Submit a question to the AI chatbot."""
    service = _get_chatbot_service()
    result = await service.answer(db, question=body.question, user_id=body.user_id)
    return ChatAnswer(
        answer=result["answer"],
        intent=result["intent"],
        escalated=result["escalated"],
    )


@router.get("/logs", response_model=List[ChatLogResponse])
def list_chat_logs(
    user_id: Optional[int] = Query(None),
    intent: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List chat logs with optional filters."""
    query = db.query(ChatLog)
    if user_id is not None:
        query = query.filter(ChatLog.user_id == user_id)
    if intent:
        query = query.filter(ChatLog.intent == intent)
    return query.order_by(ChatLog.created_at.desc()).limit(limit).all()


@router.get("/logs/escalated", response_model=List[ChatLogResponse])
def list_escalated_logs(db: Session = Depends(get_db)):
    """List only escalated chat logs."""
    return (
        db.query(ChatLog)
        .filter(ChatLog.escalated.is_(True))
        .order_by(ChatLog.created_at.desc())
        .all()
    )


@router.put("/logs/{log_id}/rating", response_model=ChatLogResponse)
def rate_chat_log(log_id: int, body: ChatRating, db: Session = Depends(get_db)):
    """Rate a chatbot answer."""
    log = db.query(ChatLog).filter(ChatLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Chat log not found")
    if body.rating < 1 or body.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    log.rating = body.rating
    db.commit()
    db.refresh(log)
    return log
