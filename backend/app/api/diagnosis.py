from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import get_db
from app.models.diagnosis import DiagnosisHistory, DiagnosisChatMessage
from app.core.deps import get_current_user
from app.models.user import User

from app.services.diagnosis_agent import run_diagnosis

from pydantic import BaseModel, Field

class CreateDiagnosisHistoryRequest(BaseModel):
    pest: str = Field(min_length=1, max_length=100)
    crop: str = Field(min_length=1, max_length=100)
    region: str = Field(min_length=1, max_length=100)
    image_url: str | None = None

class CreateChatMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])

@router.get("/history")
async def get_diagnosis_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """현재 로그인한 사용자의 모든 진단 기록 조회."""
    query = (
        select(DiagnosisHistory)
        .where(DiagnosisHistory.user_id == current_user.id)
        .order_by(DiagnosisHistory.created_at.desc())
    )
    result = await db.execute(query)
    histories = result.scalars().all()
    
    # 딕셔너리 변환 시 to_dict()가 구현되어 있다고 가정 (또는 직접 구성)
    return [
        {
            "id": h.id,
            "pest": h.pest,
            "crop": h.crop,
            "region": h.region,
            "analysis_result": h.analysis_result,
            "image_url": h.image_url,
            "created_at": h.created_at.isoformat()
        } for h in histories
    ]

@router.post("/history")
async def create_diagnosis_history(
    payload: CreateDiagnosisHistoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """진단 결과 저장 (VLM 완료 후 호출 -> LangGraph 오케스트레이션 진행)."""
    # 프론트에서 받은 순수 키워드
    pest = payload.pest
    crop = payload.crop
    region = payload.region
    
    # 2. 백엔드 LangGraph 엔진을 통해 병렬 데이터 수집 및 분석결과(LLM 결과) 생성
    analysis_result = await run_diagnosis(pest, crop, region)

    new_history = DiagnosisHistory(
        user_id=current_user.id,
        pest=pest,
        crop=crop,
        region=region,
        analysis_result=analysis_result,
        image_url=payload.image_url
    )
    db.add(new_history)
    await db.commit()
    await db.refresh(new_history)
    
    parsed_text = analysis_result.get("result_text", "")
    if parsed_text:
        initial_msg = DiagnosisChatMessage(
            diagnosis_id=new_history.id,
            role="assistant",
            content=parsed_text
        )
        db.add(initial_msg)
        await db.commit()
    
    return {
        "id": new_history.id,
        "pest": new_history.pest,
        "crop": new_history.crop,
        "region": new_history.region,
        "analysis_result": new_history.analysis_result,
        "image_url": new_history.image_url,
        "created_at": new_history.created_at.isoformat()
    }

@router.get("/history/{history_id}/chat")
async def get_chat_messages(
    history_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """특정 진단 기록에 연결된 모든 채팅 메시지 조회."""
    # 먼저 해당 진단 기록이 본인 것인지 확인
    check_query = select(DiagnosisHistory).where(
        (DiagnosisHistory.id == history_id) & (DiagnosisHistory.user_id == current_user.id)
    )
    check_result = await db.execute(check_query)
    if not check_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")

    query = (
        select(DiagnosisChatMessage)
        .where(DiagnosisChatMessage.diagnosis_id == history_id)
        .order_by(DiagnosisChatMessage.created_at.asc())
    )
    result = await db.execute(query)
    messages = result.scalars().all()
    
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat()
        } for m in messages
    ]

@router.post("/history/{history_id}/chat")
async def add_chat_message(
    history_id: int,
    payload: CreateChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """채팅 메시지 추가."""
    # 권한 확인
    check_query = select(DiagnosisHistory).where(
        (DiagnosisHistory.id == history_id) & (DiagnosisHistory.user_id == current_user.id)
    )
    check_result = await db.execute(check_query)
    if not check_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="진단 기록을 찾을 수 없습니다.")

    # 1. 사용자 메시지 저장
    new_msg = DiagnosisChatMessage(
        diagnosis_id=history_id,
        role="user",
        content=payload.content
    )
    db.add(new_msg)
    await db.commit()
    await db.refresh(new_msg)
    
    # 사용자가 보낸 메시지인 경우에만 AI 답변 생성
    if new_msg.role == "user":
        # 기존 대화 내역 조회
        from sqlalchemy import asc
        hist_query = select(DiagnosisChatMessage).where(
            DiagnosisChatMessage.diagnosis_id == history_id
        ).order_by(asc(DiagnosisChatMessage.created_at))
        hist_res = await db.execute(hist_query)
        db_msgs = hist_res.scalars().all()
        
        # LLM 호출 준비
        from app.core.config import settings
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        from langchain_core.output_parsers import StrOutputParser
        
        api_key = settings.OPENROUTER_API_KEY
        model_name = settings.OPENROUTER_PEST_RAG_MODEL

        ai_reply = "API 키가 없어 답변할 수 없습니다."
        if api_key != "dummy" and api_key:
            try:
                llm = ChatOpenAI(
                    model=model_name,
                    api_key=api_key,
                    base_url=settings.OPENROUTER_URL,
                    temperature=0.3
                )
                
                # 시스템 프롬프트 구성 (전문 농업 진단사 역할)
                chat_msgs = [
                    SystemMessage(content="당신은 전문 식물 의사 및 농업 컨설턴트입니다. 사용자의 작물 병해충 진단 결과에 기반하여, 추가적인 방제 요령, 농약 혼용 방법, 예방 대책 등에 대해 친절하고 전문적으로 답변해 주세요. 이전 대화 맥락을 기억하고 이어나가세요.")
                ]
                
                # 대화 기록 변환
                for m in db_msgs:
                    if m.role == "user":
                        chat_msgs.append(HumanMessage(content=m.content))
                    elif m.role == "assistant":
                        chat_msgs.append(AIMessage(content=m.content))
                        
                # 답변 생성
                chain = llm | StrOutputParser()
                ai_reply = await chain.ainvoke(chat_msgs)
            except Exception as e:
                print(f"Chat generation error: {e}")
                ai_reply = "AI 답변 생성 중 오류가 발생했습니다."

        # 2. AI 메시지 저장
        ai_msg = DiagnosisChatMessage(
            diagnosis_id=history_id,
            role="assistant",
            content=ai_reply
        )
        db.add(ai_msg)
        await db.commit()
        await db.refresh(ai_msg)
        
        return {
            "user_msg": {
                "id": new_msg.id,
                "role": new_msg.role,
                "content": new_msg.content,
                "created_at": new_msg.created_at.isoformat()
            },
            "ai_msg": {
                "id": ai_msg.id,
                "role": ai_msg.role,
                "content": ai_msg.content,
                "created_at": ai_msg.created_at.isoformat()
            }
        }
    
    return {
        "user_msg": {
            "id": new_msg.id,
            "role": new_msg.role,
            "content": new_msg.content,
            "created_at": new_msg.created_at.isoformat()
        }
    }

@router.delete("/history/{history_id}")
async def delete_diagnosis_history(
    history_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """진단 기록 하드 딜리트."""
    # 본인 것인지 확인 후 삭제
    query = delete(DiagnosisHistory).where(
        (DiagnosisHistory.id == history_id) & 
        (DiagnosisHistory.user_id == current_user.id)
    )
    result = await db.execute(query)
    
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="기록을 찾을 수 없거나 삭제 권한이 없습니다."
        )
        
    await db.commit()
    return {"status": "success", "message": f"History {history_id} deleted."}
