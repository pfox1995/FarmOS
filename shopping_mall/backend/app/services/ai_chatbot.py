"""AI-powered chatbot service with fallback to rule-based responses."""
import logging
from sqlalchemy.orm import Session

from app.models.chat_log import ChatLog
from app.models.order import Order
from app.models.shipment import Shipment
from app.models.product import Product

logger = logging.getLogger(__name__)


class ChatbotService:
    """Chatbot that uses LLM for intent classification and answer generation."""

    def __init__(self, llm_client=None, rag_service=None):
        self.llm = llm_client
        self.rag = rag_service

    async def answer(self, db: Session, question: str, user_id: int | None = None) -> dict:
        """Process a user question and return an answer with intent and escalation info."""
        # Step 1: Classify intent
        intent = await self._classify_intent(question)

        # Step 2: Generate answer based on intent
        escalated = False
        if intent == "delivery":
            answer_text = await self._handle_delivery(db, question, user_id)
        elif intent == "stock":
            answer_text = await self._handle_stock(db, question)
        elif intent in ("storage", "season", "exchange"):
            answer_text = await self._handle_rag(question, intent)
        else:
            answer_text = "해당 문의는 상담원 연결이 필요합니다. 고객센터(1588-0000)로 전화해 주시거나, 잠시만 기다려 주시면 상담원이 연결됩니다."
            escalated = True

        # Step 3: Save chat log
        log = ChatLog(
            user_id=user_id,
            intent=intent,
            question=question,
            answer=answer_text,
            escalated=escalated,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        return {
            "answer": answer_text,
            "intent": intent,
            "escalated": escalated,
        }

    async def _classify_intent(self, question: str) -> str:
        """Classify intent via LLM or fallback to keyword matching."""
        if self.llm:
            try:
                return await self.llm.classify_intent(question)
            except Exception as e:
                logger.warning(f"LLM intent classification failed: {e}")

        return self._keyword_classify(question)

    def _keyword_classify(self, question: str) -> str:
        """Rule-based intent classification using keywords."""
        q = question.lower()
        if any(kw in q for kw in ["배송", "택배", "송장", "운송장", "도착", "언제 와"]):
            return "delivery"
        if any(kw in q for kw in ["재고", "품절", "입고", "수량", "남아"]):
            return "stock"
        if any(kw in q for kw in ["보관", "저장", "냉장", "냉동", "유통기한"]):
            return "storage"
        if any(kw in q for kw in ["제철", "시즌", "계절", "수확", "언제 나"]):
            return "season"
        if any(kw in q for kw in ["교환", "환불", "반품", "취소", "클레임"]):
            return "exchange"
        return "other"

    async def _handle_delivery(self, db: Session, question: str, user_id: int | None) -> str:
        """Handle delivery-related queries."""
        if user_id:
            orders = (
                db.query(Order)
                .filter(Order.user_id == user_id, Order.status.in_(["shipping", "paid"]))
                .order_by(Order.created_at.desc())
                .limit(3)
                .all()
            )
            if orders:
                info_parts = []
                for o in orders:
                    shipment = db.query(Shipment).filter(Shipment.order_id == o.id).first()
                    if shipment:
                        info_parts.append(
                            f"주문#{o.id}: {shipment.carrier} {shipment.tracking_number} (상태: {shipment.status})"
                        )
                    else:
                        info_parts.append(f"주문#{o.id}: 상태 '{o.status}' - 송장 미등록")
                context = "\n".join(info_parts)

                if self.llm:
                    try:
                        prompt = (
                            f"고객의 배송 현황 정보:\n{context}\n\n"
                            f"고객 질문: {question}\n\n"
                            "위 정보를 바탕으로 친절하게 답변하세요:"
                        )
                        return await self.llm.generate(prompt, system="농산물 쇼핑몰 고객지원 챗봇입니다.")
                    except Exception:
                        pass

                return f"고객님의 최근 배송 현황입니다:\n{context}\n\n자세한 사항은 택배사 홈페이지에서 송장번호로 조회해 주세요."

        return (
            "주문 후 1-3일 이내에 발송되며, 발송 후 1-2일 이내에 수령 가능합니다. "
            "마이페이지 > 주문내역에서 송장번호를 확인하실 수 있습니다."
        )

    async def _handle_stock(self, db: Session, question: str) -> str:
        """Handle stock-related queries."""
        # Try to find product name in question
        products = db.query(Product).filter(Product.stock > 0).order_by(Product.sales_count.desc()).limit(5).all()
        product_info = ", ".join(f"{p.name}(재고:{p.stock})" for p in products)

        if self.llm:
            try:
                prompt = (
                    f"현재 인기 상품 재고 현황: {product_info}\n\n"
                    f"고객 질문: {question}\n\n답변:"
                )
                return await self.llm.generate(prompt, system="농산물 쇼핑몰 고객지원 챗봇입니다.")
            except Exception:
                pass

        return (
            f"현재 인기 상품 재고 현황: {product_info}. "
            "정확한 재고는 각 상품 페이지에서 확인해 주세요. "
            "품절 상품은 재입고 알림 신청이 가능합니다."
        )

    async def _handle_rag(self, question: str, intent: str) -> str:
        """Handle queries using RAG (storage, season, exchange)."""
        collection_map = {
            "storage": "storage_guide",
            "season": "season_info",
            "exchange": "faq",
        }
        collection = collection_map.get(intent, "faq")

        if self.rag:
            try:
                return await self.rag.query(question, collection=collection)
            except Exception as e:
                logger.warning(f"RAG query failed: {e}")

        # Fallback
        return self._rule_based_answer(question, intent)

    def _rule_based_answer(self, question: str, intent: str) -> str:
        """Rule-based fallback answers."""
        if intent == "storage":
            return (
                "일반적으로 신선 농산물은 냉장(0-5도) 보관을 권장합니다. "
                "과일류는 신문지로 감싸 냉장 보관, 채소류는 키친타월로 감싸 밀폐용기에 보관하세요. "
                "자세한 보관법은 상품 상세 페이지를 참고해 주세요."
            )
        if intent == "season":
            return (
                "봄: 딸기, 냉이, 봄동 / 여름: 수박, 참외, 토마토 / "
                "가을: 사과, 배, 감 / 겨울: 감귤, 시금치, 무. "
                "제철 농산물이 가장 맛있고 영양가가 높습니다."
            )
        if intent == "exchange":
            return (
                "신선식품 특성상 단순 변심으로 인한 교환/환불은 어렵습니다. "
                "상품 하자 시 수령 후 24시간 이내에 사진과 함께 고객센터로 문의해 주세요."
            )
        return "고객센터(1588-0000)로 문의해 주세요."
